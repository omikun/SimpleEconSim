# Selected-goods aggregate stock-flow audit

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use, food inflows and consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented. Food includes public stores, regional granaries and one
per-region civilian meal total each turn; army rations are separate.

| Seed | Shock | Arm | Cotton | Cloth | Food | Wood | Issues |
|---:|---|---|---:|---:|---:|---:|---:|
| 4242 | furniture demand | control | 19/19 (max 0.0) | 16/19 (max 6.0) | 3/19 (max 472.0) | 18/19 (max 1.0) | 0 |
| 4242 | furniture demand | treatment | 19/19 (max 0.0) | 16/19 (max 6.0) | 7/19 (max 315.0) | 19/19 (max 0.0) | 0 |
| 4242 | wood supply | control | 19/19 (max 0.0) | 16/19 (max 6.0) | 3/19 (max 472.0) | 18/19 (max 1.0) | 0 |
| 4242 | wood supply | treatment | 19/19 (max 0.0) | 16/19 (max 6.0) | 5/19 (max 470.0) | 18/19 (max 1.0) | 0 |
| 4243 | furniture demand | control | 19/19 (max 0.0) | 13/19 (max 8.0) | 8/19 (max 57.0) | 18/19 (max 1.0) | 0 |
| 4243 | furniture demand | treatment | 19/19 (max 0.0) | 12/19 (max 8.0) | 4/19 (max 57.0) | 19/19 (max 0.0) | 0 |
| 4243 | wood supply | control | 19/19 (max 0.0) | 13/19 (max 8.0) | 8/19 (max 57.0) | 18/19 (max 1.0) | 0 |
| 4243 | wood supply | treatment | 19/19 (max 0.0) | 11/19 (max 8.0) | 5/19 (max 57.0) | 18/19 (max 2.0) | 0 |
| 4244 | furniture demand | control | 19/19 (max 0.0) | 16/19 (max 4.0) | 6/19 (max 452.0) | 19/19 (max 0.0) | 0 |
| 4244 | furniture demand | treatment | 19/19 (max 0.0) | 16/19 (max 4.0) | 6/19 (max 464.0) | 19/19 (max 0.0) | 0 |
| 4244 | wood supply | control | 19/19 (max 0.0) | 16/19 (max 4.0) | 6/19 (max 452.0) | 19/19 (max 0.0) | 0 |
| 4244 | wood supply | treatment | 19/19 (max 0.0) | 16/19 (max 4.0) | 4/19 (max 448.0) | 19/19 (max 0.0) | 0 |
| 4245 | furniture demand | control | 19/19 (max 0.0) | 14/19 (max 6.0) | 17/19 (max 19.0) | 18/19 (max 2.0) | 0 |
| 4245 | furniture demand | treatment | 19/19 (max 0.0) | 13/19 (max 6.0) | 15/19 (max 13.0) | 17/19 (max 2.0) | 0 |
| 4245 | wood supply | control | 19/19 (max 0.0) | 14/19 (max 6.0) | 17/19 (max 19.0) | 18/19 (max 2.0) | 0 |
| 4245 | wood supply | treatment | 19/19 (max 0.0) | 14/19 (max 6.0) | 17/19 (max 14.0) | 18/19 (max 2.0) | 0 |
| 4246 | furniture demand | control | 19/19 (max 0.0) | 11/19 (max 7.0) | 3/19 (max 1144.0) | 15/19 (max 3.0) | 0 |
| 4246 | furniture demand | treatment | 19/19 (max 0.0) | 12/19 (max 7.0) | 4/19 (max 472.0) | 14/19 (max 4.0) | 0 |
| 4246 | wood supply | control | 19/19 (max 0.0) | 11/19 (max 7.0) | 3/19 (max 1144.0) | 15/19 (max 3.0) | 0 |
| 4246 | wood supply | treatment | 19/19 (max 0.0) | 12/19 (max 7.0) | 5/19 (max 667.0) | 17/19 (max 3.0) | 0 |

Across this sample, cotton closes in 380/380 intervals, cloth in 278/380, and wood in 354/380. Food closes in 146/380; its largest absolute residual is 1144 units.
There are 234 nonzero food residuals at the 1e-6 tolerance. Summed interval granary-stock changes are 20431 units; 2352 traced deposit/release transfers report 30991 units of internal turnover. Harvest deposits debit producer inventories and seasonal releases credit government food inventory, so these moves remain inside the census boundary.

Simulation source commit(s): `258a9b781059c41bdf07e6a094ed1a6f1a037246`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual is closing stock minus prior closing stock and traced net flow. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.
