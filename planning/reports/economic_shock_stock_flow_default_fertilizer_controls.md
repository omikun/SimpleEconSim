# Default-game fertilizer stock-flow audit

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use, food inflows and consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented. Food includes public stores, regional granaries and one
per-region civilian meal total each turn; army rations are separate.

| Seed | Experiment | Arm | Balanced intervals | Issues |
|---:|---|---|---:|---:|
| 4242 | wood_supply_reduction | control | 19/19 | 0 |
| 4243 | wood_supply_reduction | control | 19/19 | 0 |
| 4244 | wood_supply_reduction | control | 19/19 | 0 |
| 4245 | wood_supply_reduction | control | 19/19 | 0 |
| 4246 | wood_supply_reduction | control | 19/19 | 0 |

| Good | Balanced intervals | Total intervals | Max absolute residual |
|---|---:|---:|---:|
| fertilizer | 95 | 95 | 0 |

Complete stock-flow closure: 5/5 runs. Structural or coverage issues: 0. A run can have no structural issues and still fail because one or more good-stock intervals do not balance.

This selected-goods view is a diagnostic screen. A nonzero residual identifies a stock-flow gap; zero residuals can still hide offsetting unsupported flows. Traced before/after fertilizer-reserve changes are included in this sample's balance.

Simulation source commit(s): `7dc498806631d1c929d9e8c4cd5fea313a977cee`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual is closing stock minus prior closing stock and traced net flow. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.


Coverage note: these are five wood-supply-control baseline traces (one per seed, 4242–4246). The separate seed-4242 four-arm all-goods run also closes fertilizer in all 76 intervals. This report does not certify fertilizer behavior in the other treatment arms for seeds 4243–4246.
