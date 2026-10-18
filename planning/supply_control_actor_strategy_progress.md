# Supply control implementation progress

## Phase 0 — fixture and operation audit (complete, 2026-10-18)

- Added a deterministic normal-engine fixture using the authored Meridian/Vesper world: at least two named cotton growers, two mills, a route, and a government. A separate poor-rainfall variant confirms finite plot water allocation falls. The first seasonal tick completes without currency audit violations.
- Turn order verified in `micro/region/stepper.py` and `sim_engine.py`: petitions and rent assessment precede labor/planning; water allocation precedes production; offtake/lien/share settlement precedes the spot auction; route posting follows the auction; wages, obligations, tax, and life follow. Route cargo delivered after local ticks can enter a destination's next auction, not its already-cleared current auction.
- Audit found no cash freight charge at route posting. Phase 1 now charges a funded per-unit freight payment to the source-region public carrier when one exists; a route fixture without a carrier remains a free test-only movement.
- A lease updates `plot.controlled_by_id` but keeps tenant cultivation and does not redirect that tenant's crop to the lessee. The planner must value a bare lease as zero input supply unless the lessee actually cultivates or contracts for the crop.

## Phase 1 — actor accounts (core implementation, further coverage pending)

- Added stable settlement-event IDs independent of compact tracing, opening snapshots, and sealed turn accounts. Spot fills, offtake delivery, advances, title/water transfer, route freight, wages, owner loans/financing/dividends, claims, taxes, and charter fees have named postings. The normal engine fixture and a prepaid crop test reconcile named cash, goods, and debt. Save/load uses the region's existing pickle state; serialization reads without posting.
- Web and desktop show named actor cash, crop receipts, input use, wages, debt, and rights. The displayed operating result is explicitly marked incomplete until all cash costs and inventory consumption paths are covered. `TrueCostLedger` remains a separate social estimate, not a second source of cash profit.
- Still to close before the phase gate: complete production cost basis when initial stock lacks a paid acquisition, company scrip and maintenance cash flows, actor-specific cross-region lot links, and a full per-actor cash bridge including FX and bank transactions. The current buffer is bounded at 2,000 events per tile.

## Phase 2 — proposals and grower agency (core implementation, further coverage pending)

- Added staged proposals for advances/offtake, land sales/leases, and water rights. Corporate AI and the player-facing land/water commands submit offers without an immediate transfer. The next turn checks seller reservation value, accepts, rejects, or counters once; buyer cash, title, rights, and harvest commitments are revalidated before settlement. Traced decisions include the outside value and reason. Tests cover a secure grower's refusal, a cash-poor grower's acceptance, a countered title sale, and rejected water diversion.
- Still to close before the phase gate: eliminate direct-call bypasses in the low-level settlement APIs, protect food/household water minima, preserve a pending offer through save/load tests, and expose a full proposal timeline with named actors in both clients.

## Phase 3 — corporate comparison

Pending; current urgency scores still choose institutional actions without a common incremental-value baseline.

## Phase 4 — playable scenario and UI

Pending.

## Phase 5 — balance and audits

Pending.
