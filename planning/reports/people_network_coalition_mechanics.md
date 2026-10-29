# Coalition mechanics verification: rules version 2

Date: October 29, 2026. [Rules specification](../people_network_coalition_mechanics.md) · [play guide](../../docs/people_network_lab.md).

## Delivered behavior

Groups now request scarce services, representation, repair priorities and limits on sustained mobilization. The service allocation always totals four shares; minimum group requests total six. Contractual support can be withheld despite high personal influence. Credible programs matter before election, while actual delivery, history and overpromising affect belief in them. Agreements remain live obligations after honoring them and survive removal/restoration. Volunteers cannot campaign indefinitely, including when no public project is active.

Council seats are distributed across all four communities. The new Groups panel exposes demands, funding, records for both leaders, agreement state and direct allocation/negotiation controls. The overview warns about scarce shares and upcoming breaks. Map cards display funding; rings and hover/profile text display campaign strain. The causal viewer names budget transfers, agreement outcomes and support withheld, and separates delivery/program effects from other interest forces.

## Verification

71 targeted tests pass: the existing graph, political, advice, geography, UI and desktop chart/explainer checks plus 15 coalition contracts and a new Groups/control-cycle UI check. Checks cover budget conservation and action rejection, inter-group consequences, individual agency, conditional refusal, continued delivery, two-round repair of agreements, opposition limitations, no renewed grace after restoration, representation/workload demands, credibility/overpromising, strain without a project, cross-community council coverage, save/resume/replay, explicit old-save rejection and exact interest decomposition.

All five acceptance cases replay with identical state digests under version 2. The [machine-readable summary](people_network_acceptance.json) includes allocations, group agreement results, exhaustion counts, version and timing. It replaces the version-1 hashes; the rule changes intentionally change political outcomes.

| Start / policy | Rounds | Observed result |
|---|---:|---|
| Governing / public policy | 24 | Remains in office; maintains a funded coalition and completes the bridge late |
| Governing / pass | 24 | Loses office in round 14 |
| Displaced / coalition policy | 24 | Returns in round 11 and honors group agreements |
| Displaced / pass | 24 | Remains out of office |
| Governing / checked cycle | 32 | Loses office in round 11, returns in round 23, governs with inherited obligations, loses again in round 30 |

The final case is not forced to end in victory. It retains only legal actions and actual engine results. Restored authority does not repair unmet obligations or keep a coalition together automatically. The fixture verifies honored agreements after restoration as well as further vulnerability. It is not evidence that one group breach was the sole necessary cause of the final loss.

Rendered Groups, overview, council, network and briefing screens were inspected at 1100×800 and 1440×960, including a restored government with an agreement still repairing. Button bounds, modal input protection, direct group actions and goal cycling are checked automatically. These are SDL/headless controller and visual checks, not human enjoyment testing.

## Limits and next assessment

Four service shares and three-round campaign capacity are transparent laboratory abstractions, not financial claims about the wider economic engine. The scenario retains two candidates and authored group terms. No arbitrary guaranteed group voting, omniscient player control of opponents, or automatic positive vote assignment was added. The rival remains an inspectable public heuristic; forecasts remain conditional five-round comparisons.

Human playtesting remains open. Test whether players understand why a funded group can still withhold until delivery is sustained, whether competing demands create credible alternative coalitions, and whether volunteer rotation creates meaningful decisions rather than busywork. Full-game integration remains deferred.
