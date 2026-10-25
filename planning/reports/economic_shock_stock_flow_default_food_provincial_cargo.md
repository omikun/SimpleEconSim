# Default-game food stock-flow audit with provincial cargo

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use, food inflows and consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented. Food includes public stores, regional granaries and one
per-region civilian meal total each turn; army rations are separate.

| Seed | Experiment | Arm | Balanced intervals | Issues |
|---:|---|---|---:|---:|
| 4242 | wood_supply_reduction | control | 4/19 | 0 |

| Good | Balanced intervals | Total intervals | Max absolute residual |
|---|---:|---:|---:|
| food | 4 | 19 | 160 |

Complete stock-flow closure: 0/1 runs. Structural or coverage issues: 0. A run can have no structural issues and still fail because one or more good-stock intervals do not balance.

This selected-goods view is a diagnostic screen. A nonzero residual identifies a stock-flow gap; zero residuals can still hide offsetting unsupported flows.

Simulation source commit(s): `ebd660c353cbbc676149d24c12f1086474a8be80`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual is closing stock minus prior closing stock and traced net flow. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.


The matched-source census comparison confirms that provincial cargo explains the shipment-sized residuals:

| Turn | Dispatch | Arrival | Cargo stock change | Old residual | Cargo-inclusive residual |
|---:|---:|---:|---:|---:|---:|
| 16 | 472 | 0 | +472 | -472 | 0 |
| 17 | 197 | 472 | -275 | +266 | -9 |
| 18 | 0 | 197 | -197 | +191 | -6 |
| 20 | 373 | 0 | +373 | -378 | -5 |

Coverage note: one clean-source seed-4242 wood-supply-control baseline arm, matched to the prior source by its pre-shock state digest. The whole-world census includes emergency-meal queues and pending provincial food shipments. The remaining turn-3 residual is -160 units, and this one-arm result does not establish closure across seeds or treatment arms.
