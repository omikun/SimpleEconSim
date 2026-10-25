# Selected-goods aggregate stock-flow audit

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use, food inflows and consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented, and does not cover goods beyond cotton, cloth, food and
wood. Food includes regional granary stocks and one
per-region civilian meal total each turn; army rations are separate.

| Seed | Shock | Arm | Cotton | Cloth | Food | Wood | Issues |
|---:|---|---|---:|---:|---:|---:|---:|
| 812 | cotton supply | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 812 | cotton supply | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 812 | mill cotton demand | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 812 | mill cotton demand | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 813 | cotton supply | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 813 | cotton supply | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 813 | mill cotton demand | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 813 | mill cotton demand | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 814 | cotton supply | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 814 | cotton supply | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 814 | mill cotton demand | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 814 | mill cotton demand | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 815 | cotton supply | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 815 | cotton supply | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 815 | mill cotton demand | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 815 | mill cotton demand | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 816 | cotton supply | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 816 | cotton supply | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 816 | mill cotton demand | control | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |
| 816 | mill cotton demand | treatment | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 19/19 (max 0.0) | 0 |

Across this sample, cotton closes in 380/380 intervals, cloth in 380/380, and wood in 380/380. Food closes in 380/380; its largest absolute residual is 0 units.
There are 0 nonzero food residuals at the 1e-6 tolerance. Summed interval granary-stock changes are 1601 units; 560 traced deposit/release transfers report 3361 units of internal turnover. Harvest deposits debit producer inventories and seasonal releases credit government food inventory, so these moves remain inside the census boundary.

Simulation source commit(s): `8320f3153f5de943a5bc3a24bbaeaf3a782955c6`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual is closing stock minus prior closing stock and traced net flow. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.
