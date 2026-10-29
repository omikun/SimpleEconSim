# Relationship strength and conditional strategic advice

Date: October 28, 2026.

## Problem

The original overview's suggestions really were shallow: ask the least-opposed reachable councillor and rally a well-connected ally. Although the graph engine already models directed trust, normalized attention, interests, opposition, commitments and actual work, the advisor did not evaluate these interactions. A larger marker or fancier rank does not create strategic depth.

## Delivered change

Line thickness now reflects directional trust multiplied by communication capacity and availability, in the currently selected political or repair context. Map, large network and personal contact views use the same width function. Hover/selection adds a small emphasis. A closed channel has zero width. The legend states what thickness means; it is relationship strength, not a claim that every strong tie is currently transmitting a large net pressure.

Advice now considers every legal one-action request, rallying assignment and release under the current action budget and pending commitments. Each is run through a separate copy of the actual engine for five rounds and compared with waiting over those same rounds. Existing accepted commands are retained; Sen starts with the same information boundary as in the live game, then follows the public rival policy in each branch. No future player actions are assumed. Forecasts do not change live state, consume global randomness, create actual history events or affect the rival.

The comparison evaluates the whole trajectory, including time holding a five-vote majority, office retention/recovery, votes sustained across the final two forecast rounds, threshold readiness, real repair staffing by skill/location, task progress/completion, deadline/maintenance failure and existing broken promises. Different goals change the relative value of political versus repair results. Organizing can be penalized for removing a critical repair worker. Releasing an organizer can be the best move when their labor is needed.

Scores are explicit authored utility weights in `people_network/advice.py`, not a discovered optimum. Office and quorum consequences outweigh small continuous support gains; failures and broken promises carry costs. Two different people are shown as alternatives when useful positive comparisons exist. The advisor may recommend two organizers rather than artificially forcing one request and one organizer. It can also return no useful action, especially after all action points are spent.

Cards explain observed comparative results and costs, identify protected supporters where possible, and show their five-round assumption. Results are recalculated after accepted actions; speculative advice is disabled during historical inspection. Exact state and rival-information snapshots key a bounded in-memory cache. On the development machine the initial 32-person comparison took approximately 440 ms and cached complete graph rendering approximately 7 ms; no branch simulation occurs on an unchanged frame. These are local observations, not performance guarantees for larger populations.

## Verification

55 targeted tests pass: the previous 51 plus four additional advice/line-width contracts. New counterexamples demonstrate that:

- A more-opposed person who trusts the player can be a better request target than the least-opposed person with almost no trust.
- Freeing a needed hauler is preferred to rallying the last available repair worker when the crossing needs both skills immediately.
- Advice is read-only, respects budgets and the information boundary, preserves global randomness, and cannot have its cache poisoned by a caller mutating a returned card.
- Thicker ties track trust, capacity, context and availability rather than using one fixed line width.

All five existing scripted political runs retain their exact authoritative state digests and replay results. No persuasion coefficients, political rules, rival policy or scenario content were changed. Rendered terrain and network views were inspected at 1100×800 and 1440×960.

## Actual limits, not solved by the advisor

This is bounded one-move lookahead against one known rival policy. It does not search future player combinations, compare new pledges/concessions, test alternative rival strategies or guarantee robust long-term coalitions. A pledge that breaks when no further actions are taken may be fulfillable by a subsequent appointment; the forecast's assumption must be read accordingly. The existing real-time trace explains actual outcomes, while the card explains a conditional hypothetical branch.

The laboratory itself still has only two candidates, one council and two repair priorities. There is little cost to rallying when no repair labor is needed. Neither this forecaster nor a higher node centrality score supplies competing long-term interests, real organizational operating costs, deeper faction bargaining or more ways to govern. Those are substantive future gameplay decisions requiring design and playtesting, not claims made by this update.
