# Supply control implementation progress

## Phase 0 — fixture and operation audit (complete, 2026-10-18)

- Added a deterministic normal-engine fixture using the authored Meridian/Vesper world: at least two named cotton growers, two mills, a route, and a government. A separate poor-rainfall variant confirms finite plot water allocation falls. The first seasonal tick completes without currency audit violations.
- Turn order verified in `micro/region/stepper.py` and `sim_engine.py`: petitions and rent assessment precede labor/planning; water allocation precedes production; offtake/lien/share settlement precedes the spot auction; route posting follows the auction; wages, obligations, tax, and life follow. Route cargo delivered after local ticks can enter a destination's next auction, not its already-cleared current auction.
- Audit found no cash freight charge at route posting. `transport_cost_per_unit` affects traders' expected margin but is not an actual payment. The actor account must identify this gap until funded route freight is implemented.
- A lease updates `plot.controlled_by_id` but keeps tenant cultivation and does not redirect that tenant's crop to the lessee. The planner must value a bare lease as zero input supply unless the lessee actually cultivates or contracts for the crop.

## Phase 1 — actor accounts

In progress.

## Phase 2 — proposals and grower agency

Pending.

## Phase 3 — corporate comparison

Pending.

## Phase 4 — playable scenario and UI

Pending.

## Phase 5 — balance and audits

Pending.
