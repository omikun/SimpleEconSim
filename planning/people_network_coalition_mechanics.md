# Coalition maintenance: laboratory rules version 2

Implemented October 29, 2026. See the [play guide](../docs/people_network_lab.md) and [verification report](reports/people_network_coalition_mechanics.md).

## Concrete stakes

The four organizations now have authored material and institutional demands: cultivators need two service shares and favor field access; traders need two shares and favor market access; craft members need one share and a limit of two simultaneous organizers working for one candidate; civic members need one share and representation through a liaison. Six minimum funding shares compete for a recurring envelope of four. Giving a share to one group requires taking it from another.

These shares are a fixed laboratory abstraction for public services. They are not currency or a second economic ledger. `government.allocations` conserves four nonnegative integer shares. Allocations persist through rounds and government changes; only the incumbent can transfer one share per action. Representation uses the existing two liaison posts. Actual repair cooperation still depends on individual commitments, skills, locations and effort.

The nine-person council now has at least two councillors in each community, with the ninth in an overlapping civic/craft network. Initial support remains five incumbent/four rival. The player must manage relationships outside the capital rather than obtaining nearly every necessary vote from one town.

## Agreements and individual agency

One group agreement per candidate/group can be offered through an available coordinator contact. The agreement specifies the group's funding minimum and, where applicable, representation and organizing-load limit. The repair-priority preference affects satisfaction but is not silently added to the binding agreement. Terms are fixed authored bundles rather than free-form negotiation.

Credible agreements increase the attractiveness of a program through individual interests. A proposal addressing demands the incumbent is failing is more compelling than merely matching services already delivered. Credibility declines with past breaches, broken personal promises and promised funding above the four-share budget. No positive rule assigns an organization's votes or overrides personal pressure thresholds.

The incumbent has two governing rounds to establish delivery. An opposition agreement waits for office. Two consecutive fulfilled governing rounds honor the agreement; continued fulfillment is required. An unmet agreement after its grace period, or a later breach of an honored agreement, can force participating members to withhold support. Repairing a breach requires two fulfilled rounds, not simply making another offer. Members may choose a different candidate through the normal pressure rules.

Displacement suspends public-delivery conditions the candidate cannot enforce, preserves breach history and elapsed governing time, and resets consecutive delivery. Restoration resumes the existing obligation without a fresh grace window. Fulfilled public service can rebuild the record, but old promises and limited action capacity may make a restoration difficult to stabilize.

## Remembered delivery and influence

Each organization tracks a delivery record for each candidate. Current funding, repair priority, representation and workload determine the incumbent's gradual record. The opposition's historical record fades slowly, with additional penalties for overmobilizing craft members. These records affect members' political interest anchors; pressure still evolves on the same graph. Shared memberships can transmit competing expectations without duplicating people or ballots.

Current authored response values are 0.22 for delivery adaptation, 0.28 for group-record influence, and 0.28 for program influence before credibility, overlap and conditional-status adjustments. Values are bounded, inspectable tuning defaults, not empirical social estimates. Source, incoming-edge, base-interest, group-delivery, agreement and clamp contributions can be reconstructed separately.

## Organizing cannot run indefinitely

Campaign strain rises by one per active rallying round and reduces reinforcement. At three active rounds a person stops organizing and needs two rounds away from campaigning. People recover while released. Assigning a tired volunteer is rejected; releasing early costs an action and permits earlier recovery. Strain also applies with no public project, so there is no unlimited free organizing mode. Ordinary work and governing are separate from this campaign break.

Organizations, memberships and ordinary peer channels persist when a person steps back. The player and rival use identical strain, budget, agreement and command rules. The rival allocates services, appoints representatives, offers feasible funding commitments and prioritizes fulfilling existing agreements while rotating organizers.

## Ownership, timing and trace

`people_network/coalitions.py` owns group delivery, terms, credibility and strain updates. Commands and declarations remain authoritative in `engine.py`. At the round boundary, apply accepted declarations, evaluate delivery and conditional deadlines, update interest anchors, then propagate pressure and resolve individual choices. Work and personal promises resolve next, followed by council votes. Strain and organizer departure resolve before new invitations are queued. Thus budget transfers can affect that round's response, new organizers activate next round, and exhausted organizers cease forwarding.

Trace accepted actions, budget transfers, agreement status changes, consequential group mood bands, support withheld, organizer exhaustion and office transitions. Checkpoints preserve gradual record/strain changes. Allegiance events link back to the agreement, allocation, representation and prior delivery evidence. The pressure explanation reconciles base interests, group delivery, conditional program and saturation exactly. Reading forecasts creates no actual events or state changes.

Saves use version 2 and include all allocations, agreements, interest components, mood records, strain/rest windows and causal cursors. Version-1 saves are explicitly rejected. Rule changes intentionally change old political trajectories; the checked playthrough and acceptance results were rebuilt rather than preserving artificial old outcomes.

## Boundaries

This remains the isolated laboratory: no household finances, national tax revenue, real government budget, imprisonment, death/succession or full-game integration. Agreement cancellation/free-form renegotiation and changing external demand schedules are not implemented. Players can restore a breached agreement by actual delivery. Human playtesting must assess whether the new choices are legible and enjoyable.

## Separate Patronage ruleset

The [Patronage ruleset](../docs/people_network_patronage.md) implements a bounded version of the [patronage plan](people_network_patronage_implementation_plan.md): personal versus constituent interests, control rights, contracts, jobs, private gains, dependence and audience-scoped promises. It uses a separate version-3 schema and launcher option; these classic version-2 rules retain their behavior.
