# Railway strikes, collective power, and independence

Status: proposed design, 2026-10-14. This document adds no runtime behavior. It extends the [labor AI plan](plunder_of_labor_ai_and_ui_plan.md); the existing 20-turn [first slice](plunder_of_labor_first_slice.md) remains its own bounded scenario.

Execution steps: [Implementation plan](railway_strikes_implementation_plan.md).

## Historical basis and limits

The October 1947–March 1948 railway strike involved roughly 20,000 workers across French West Africa, including Senegal. That is a federation-wide count. It interrupted most rail traffic for about five and a half months. Workers pursued nondiscrimination and a common employment structure. Community support sustained the struggle; professional gains could also separate railwaymen from other workers. Politicians subsequently recognized their electoral importance. These are the central tensions in [Frederick Cooper, “Our Strike” (1996)](https://doi.org/10.1017/S0021853700034800).

[Babacar Fall's oral-history research](https://www.researchgate.net/publication/236768234_Orality_and_Life_Histories_Rethinking_the_Social_and_Political_History_of_Senegal) connects the victory with workers discovering their collective strength and with the emergence of political and union activists. His discussion also cautions against substituting Sembène's fictional account for participants' experiences.

The independence settlement came much later: the Mali Federation, including Senegal, became independent on 20 June 1960; Senegal withdrew on 20 August. See [the contemporary diplomatic record](https://history.state.gov/historicaldocuments/frus1958-60v14/d59) and [Senegal chronology](https://history.state.gov/countries/senegal). A strike cannot explain the intervening constitutional and political history on its own.

Design inference: workplace struggle can produce transferable organization, confidence, and political leverage. Political goals depend on subsequent treatment, alliances, and available constitutional alternatives. No evidence here establishes a causal percentage of independence attributable to a strike. Every coefficient below is an initial game tuning value, not a historical estimate.

## 1. Player tension

Concentrating production and transport can make an economy more competitive while increasing workers' ability to coordinate and interrupt it. Preserving community livelihoods helps citizens withstand hardship and refuse poor terms. Concessions cost employers or the treasury but can restore reliable trade and strengthen trust. Suppression consumes actual personnel and supplies, can destroy organizations, and may also broaden opposition.

The objective remains competition and livelihood management. Independence is a possible political outcome in a colonial relationship. In a sovereign country the same organizational capacity instead supports bargaining, elections, or constitutional reform. Never turn every domestic strike into separatism.

## 2. State and ownership

Maintain organizations with persistent IDs, members, representatives, links to other organizations, a cash account, food inventories, and a jurisdiction. Existing people may belong to several groups; aggregates must deduplicate them. Track claims against the responsible employer, local government, or imperial authority separately.

Each organization/community cohort holds:

| Variable | Range | Meaning |
| --- | --- | --- |
| O | 0–1 | Organization: ability to coordinate, maintain representatives, and carry out agreed actions. |
| E | 0–1 | Collective confidence: belief that coordinated action can achieve its demands. |
| I | 0–1 | Support for ending the colonial constitutional relationship. Unused without that relationship. |
| A | 0–1 | Attribution of an incident to that colonial authority, based on available evidence. |
| preferences | shares summing to 1 | Preferred remaining arrangements: reform within the existing relationship, autonomous federation, or other scenario-supported arrangements. Independence share is I. |

An illustrative initial movement has O=.35, E=.30, I=.40. Initialize from scenario data, not ethnicity. These values describe a fictional example, not Senegalese public opinion.

Keep organization, confidence, material grievances, and political preference separate. Better wages can reduce grievance while leaving capable unions intact. Do not erase consciousness or membership when a law passes.

## 3. A strike must interrupt an actual dependency

For each required rail occupation r:

```text
staffing_r = min(1, available_qualified_hours_r / required_hours_r)
rail_capacity = normal_capacity * min(staffing_r for required roles)
```

Exclude striking workers. Include replacements only after actual recruitment, training where necessary, arrival, and funded payroll. No required hours means that role imposes no constraint. Use the transport engine's other bottlenecks as well: missing fuel or damaged infrastructure cannot be fixed by staffing.

Resolve inventory buffers, alternative routes, transport purchases, deliveries, sales, and taxes normally. Record undelivered orders, unpaid sales opportunities, and military supply delays. Do not deduct a second abstract “strike damage” charge. Unsold cotton remains owned inventory; an explicit spoilage rule is required to destroy goods.

For a simple forecast, 80% of exports using rail multiplied by a 75% rail service reduction implies up to 60% of exports initially exposed to interruption. This is an exposure estimate, not a booked loss or a prediction after rerouting.

The current first slice has no dedicated railway workforce. A rail scenario needs transport jobs and capacity first. Its smaller follow-up can demonstrate the same dependency with existing factory workers, without labeling factory disruption a railway strike.

## 4. Participation and endurance

Reuse household livelihood evaluation for work, subsistence, migration, and collective withholding. Add the organization-funded strike option. A strike vote authorizes a collective proposal; each household still needs an executable choice. Count only participants who actually withhold labor.

Union funds and community support transfer existing cash or food. Subsistence access provides food only through the normal production/gathering operation and its labor requirement. Care and provisioning take available household time. Outside supporters have finite inventories and budgets. A fund cannot buy food unavailable for delivery.

Show projected endurance as the earliest household shortfall under the proposed distribution, plus the number of households already short. An aggregate fund balance must not conceal unequal access. Forecast ranges must account for changing prices and donation uncertainty.

Set these event inputs from observed history, all in [0,1]. In the current first slice, which has no shared household budget, use participant-person-periods for S/H and label the UI accordingly. Use household-periods only in a scenario with actual shared accounts and consumption:

- P: average participant labor-hours divided by eligible labor-hours over the strike.
- S: fraction of participating household-periods whose essential needs were met through their own resources or delivered mutual aid.
- H: fraction of participating household-periods with an essential-needs shortfall; initially H=1-S.
- X: fraction of organizational operating capacity actually lost through imprisonment, dispersal, destruction, or departure, deduplicated by affected representative/resource. X is not a free police intensity slider.

Hunger can cause withdrawal without erasing political grievance. Defeats can leave usable experience, and a small wealthy organization can still lack a broad political constituency.

## 5. Score what the settlement delivers

At strike authorization, freeze supported demands and weights. Example: real-pay improvement .40, equal treatment .35, enforceable hours/job security .25. Each demand has baseline, target, beneficiaries, payer, and deadline. Workers must endorse the package; avoid implausibly tiny targets selected only to farm victories.

```text
fulfillment_d = clamp((delivered_d - baseline_d) / (target_d - baseline_d), 0, 1)
V = sum(weight_d * fulfillment_d)
```

For reductions such as hours, orient the measure so improvement is positive. For rights use the share of eligible people actually receiving protection; a decree alone scores zero until operative. For wages use paid purchasing power against a fixed needs basket, not a nominal offer. Weights sum to one; zero-distance targets are excluded and weights renormalized before voting. A strike with no valid demand cannot be authorized.

Assess a settlement once at its declared review date, initially after two payroll periods. Assess a failed strike when it ends. Continuing enforcement and later breaches have their own event records. Event IDs and applied flags prevent repeat rewards from reopening a panel, loading a save, or reprocessing the turn.

Update from the pre-assessment values, simultaneously:

```text
O_next = clamp(O + .20*P*S*(1-O) - .30*X*O)
E_next = clamp(E + .35*V*(1-E) - .20*(1-V)*E - .10*H*E)
```

All one-argument clamps mean [0,1]. O rewards real coordination and provisioning even in an unsuccessful struggle. E responds to delivered achievement and hardship. Repeated disputes require a fresh changed condition or unresolved claim and a new vote; the same fulfilled claim cannot earn repeated gains. Continuing a strike forever adds no per-turn victory bonus.

## 6. Decide whether organization becomes anticolonial politics

At a distinct verified political incident or settlement review, update each affected cohort:

```text
I_next = clamp(I + .25*B*A*(1-I) + .20*R*A*(1-I) - .20*F*I)
```

- B: verified shortfall in a previously accepted commitment after its deadline, weighted by its importance to this cohort. An unaccepted negotiating proposal is not a broken promise.
- R: severity of a new coercive incident experienced or credibly learned about by the cohort. Store affected people and evidence; do not repeatedly apply an ongoing incident as new violence.
- F: delivered, credible improvement in treatment by the authority governing the colonial relationship. An ordinary private pay increase does not automatically establish imperial legitimacy. Rights, remedy, and maintained equal treatment can do so. F differs from the strike's workplace achievement V.
- A: perceived responsibility of the colonial authority. Attribution varies with evidence and institutions; it is not perfect omniscience.

B, R, F are event-specific, not values charged again every tick. Persistent discriminatory laws create specific denied-rights experiences through the existing grievance system. Aggregate those experiences at a declared cadence and cap overlapping exposure; do not add another generic nationalism drift for the same event.

When I falls, redistribute that share among the available alternatives in proportion to the cohort's prior preferences; use a scenario-declared distribution if those shares were zero. When I rises, scale the remaining shares down proportionately. Dedicated federation/reform proposals can change their relative shares through separate votes. Sovereignty, federation, and territory boundaries require explicit proposals; railway links must not silently imply modern national borders.

Broaden reach through actual contact: recruitment, joint committees, political alliances, kin/community links, and shared campaigns. Each invitation takes organizer time and the receiver may decline. Coalition coverage C is the fraction of unique eligible residents belonging to or explicitly endorsing participating organizations. For larger populations use weighted cohorts and deduplicate overlaps. C is not the fraction employed on the railway.

Optional passive learning along a functioning link can move confidence toward the sender's confidence by at most .02*link_strength*(sender_E-receiver_E) per game-month. This moves information, not money, membership, or automatic support for independence. Strengthening links requires an actual organizing action. Make time conversion explicit; do not give an annual tick a daily learning rate.

An index for political agenda strength is:

```text
K = .60*O + .40*E
mobilization_index = 100 * sum(population_share_g * K_g * I_g)
```

Sum over deduplicated participating/endorsing cohorts; population shares use the entire jurisdiction's eligible resident population. A uniform coalition reduces this to `100*K*C*I`. It is a design index, not a probability of independence or a claim about historical polling. Display actual supporters and coalition composition alongside it.

## 7. Worked example

Hold coalition coverage C=.60. Begin with O=.35, E=.30, I=.40. A strike has P=.90, S=.80, H=.20, X=0, V=.80. Its settlement also delivers credible colonial reform F=.80; B=R=0.

| Stage | O | E | I | Mobilization index |
| --- | ---: | ---: | ---: | ---: |
| Before strike | .3500 | .3000 | .4000 | 7.92 |
| After delivered settlement | .4436 | .4780 | .3360 | 9.22 |

The movement becomes more capable while support for leaving decreases. An improvement in livelihoods can genuinely stabilize politics, even though unions retain power.

If a later distinct incident instead has B=.80, R=.50, A=1, F=0, then I becomes .5352. If that incident also removes X=.10 of organizational operating capacity, apply the organizational loss term once: O becomes .430292. E is unchanged in this isolated example because there is no second strike assessment. The index becomes 14.43. Later radicalization therefore activates organization built earlier, while actual repression also weakens its capacity.

These are alternative illustrative circumstances, not a forecast of Senegal's historical trajectory. Continued credible reform, sectional privilege, internal division, or loss of organizers can produce other outcomes.

## 8. Political outcomes and AI

The index changes who can put a proposal on the agenda and how credible their promised mobilization appears. It never changes sovereignty by itself. Ratification needs actual delegates/voters and an explicit constitutional rule; treaty acceptance needs parties that accept it; armed outcomes use the existing funded military and control systems.

The authority compares feasible strategies over a declared forecast horizon:

```text
expected_public_balance = receipts - payroll - administration - supplied_force_costs
strategy_value = expected_public_balance + mandate_value + security_value
                 - expected_disruption_cost - expected_political_loss
```

Only realized receipts/spending change treasury cash. Forecast terms are estimates with uncertainty, and disruption already present in lower receipts must not be counted twice. An imperial authority, a local government, and a railway employer need separate accounts and motives. Corporate profit never automatically finances police or soldiers.

Candidate actions: negotiated labor settlement; enforce equal treatment; fund a feasible productivity improvement; maintain the current offer; seek narrowly targeted replacements; use an existing lawful enforcement action; offer autonomy/federation; negotiate independence. Offer only implemented, affordable actions within the actor's authority. Coercion does not guarantee victory. Negotiation can succeed durably. Professional concessions may satisfy railway workers without benefiting peasants; coalition members evaluate their own outcomes.

Worker AI compares feasible packages against continuing action and household endurance, using expectations rather than knowledge of the future. Party alliances require member consent and can bring resources while compromising autonomy. Allies can disagree about land, taxation, language, religion, or federation. Foreign rivals may offer funded help for their own interests, without automatically controlling the movement.

Independence retains people, claims, organizations, property, debts, and funded commitments unless the settlement explicitly changes them. The new government faces labor bargaining too. Do not clear grievance, hunger, or union autonomy at a flag change.

## 9. UI, pacing, and implementation sequence

Use one shared projection for desktop and web. A strike card should show the representatives, demands, affected routes/jobs, households short of food, estimated endurance, and the next decision deadline. A settlement card should show promised versus delivered terms, who pays, who benefits, and the review date.

After resolution, explain both directions: “Equal treatment implemented; support for remaining increased. The union retains its committees and membership.” After a breach: “The missed agreement increased support for leaving among the affected coalition.” Show uncertainty and observed preferences; never report the mobilization index as a precise probability of revolt.

Present a few consequential decisions at existing scenario decision points, with warnings before deadlines. Suppress repetitive notifications. A general strike, an independence congress, and a negotiated federation should feel different and require different constituencies. Foreign competition continues through actual supply, receipts, and military readiness rather than a scripted punishment for concessions.

Implementation order:

1. **Persistent collective bargaining:** extend `StrikeRecord` in `labor_resistance.py` with demand records, participants, accounts, settlement review, and idempotent events. Audit existing `labor_politics.py` and `unrest.py` concession/repression pathways to avoid double resolution. Replace the present cash/long-hours concession shortcut for this feature with funded offers and worker acceptance.
2. **Organization and consequence:** add O/E updates, actual mutual aid, distinct household choices, and shared desktop/web explanations. Demonstrate a funded settlement restoring output while leaving a capable union. This is the next small playable labor slice.
3. **Transport scenario:** add a staffed transport dependency and replacement/rerouting operations; only then create a railway-specific scenario. Verify that supply disruption reaches taxes and military provisioning through existing flows.
4. **Political conversion:** add colonial jurisdiction/authority, explicit coalition and constitutional preferences, and settlement/breach attribution. Use existing faction/election/diplomacy seams where appropriate. Independence requires a separate complete settlement operation and longer campaign horizon.

Acceptance cases: delivered concessions reduce the relevant grievance without deleting organizations; declarations without delivery do not score victory; poor provisioning can end a strike without creating loyalty; replacements need actual people/pay/training; funds and goods conserve; rerouting reduces disruption; the same event never applies twice, including after reload; overlapping organizations never double-count residents; private wage disputes do not automatically create separatism; credible reform can persist; repression may weaken capacity while increasing exit preference; acquired independence preserves obligations; desktop/web show identical facts.

Calibration: compare matched seeds with organization learning enabled/disabled, then separately vary settlement credibility, subsistence access, transport dependence, and coalition breadth. Report differences in wages, household shortfalls, paid trade, public balance, political preferences, and constitutional outcomes over many runs. Those differences measure the mechanic's contribution inside the simulation, not the historical causal effect. Playtest whether players can explain the tradeoff and find at least two viable strategies before expanding the system.
