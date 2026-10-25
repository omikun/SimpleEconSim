# All-physical-goods aggregate stock-flow audit

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use, food inflows and consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented. Food includes public stores, regional granaries and one
per-region civilian meal total each turn; army rations are separate.

| Seed | Experiment | Arm | Balanced intervals | Issues |
|---:|---|---|---:|---:|
| 4242 | furniture_demand_increase | control | 324/361 | 0 |
| 4242 | furniture_demand_increase | treatment | 328/361 | 0 |
| 4242 | wood_supply_reduction | control | 324/361 | 0 |
| 4242 | wood_supply_reduction | treatment | 326/361 | 0 |
| 4243 | furniture_demand_increase | control | 326/361 | 0 |
| 4243 | furniture_demand_increase | treatment | 321/361 | 0 |
| 4243 | wood_supply_reduction | control | 326/361 | 0 |
| 4243 | wood_supply_reduction | treatment | 321/361 | 0 |
| 4244 | furniture_demand_increase | control | 327/361 | 0 |
| 4244 | furniture_demand_increase | treatment | 327/361 | 0 |
| 4244 | wood_supply_reduction | control | 327/361 | 0 |
| 4244 | wood_supply_reduction | treatment | 325/361 | 0 |
| 4245 | furniture_demand_increase | control | 337/361 | 0 |
| 4245 | furniture_demand_increase | treatment | 333/361 | 0 |
| 4245 | wood_supply_reduction | control | 337/361 | 0 |
| 4245 | wood_supply_reduction | treatment | 337/361 | 0 |
| 4246 | furniture_demand_increase | control | 317/361 | 0 |
| 4246 | furniture_demand_increase | treatment | 316/361 | 0 |
| 4246 | wood_supply_reduction | control | 317/361 | 0 |
| 4246 | wood_supply_reduction | treatment | 322/361 | 0 |

| Good | Balanced intervals | Total intervals | Max absolute residual |
|---|---:|---:|---:|
| food | 157 | 380 | 160 |
| wood | 354 | 380 | 4 |
| furniture | 329 | 380 | 4 |
| transport | 380 | 380 | 0 |
| wool | 380 | 380 | 0 |
| cloth | 278 | 380 | 8 |
| nitrates | 380 | 380 | 0 |
| cotton | 380 | 380 | 0 |
| iron_ore | 380 | 380 | 0 |
| iron | 380 | 380 | 0 |
| coal | 380 | 380 | 0 |
| tobacco | 380 | 380 | 0 |
| sugar | 380 | 380 | 0 |
| tea | 380 | 380 | 0 |
| fine_textiles | 380 | 380 | 0 |
| porcelain | 380 | 380 | 0 |
| rum | 380 | 380 | 0 |
| foreign_luxuries | 380 | 380 | 0 |
| fertilizer | 80 | 380 | 27 |

Complete stock-flow closure: 0/20 runs. Structural or coverage issues: 0. A run can have no structural issues and still fail because one or more good-stock intervals do not balance.

The audit includes late corvée output from recorded elite operator executions: 10170 cotton and 14556 sugar units across the sample. These outputs occur after the ordinary tile production total and otherwise appear as unexplained stock increases.

This all-physical-goods view is a diagnostic screen. A nonzero residual identifies a stock-flow gap; zero residuals can still hide offsetting unsupported flows. This trace set has no nonzero source-linked fertilizer reserve changes, so fertilizer inflow/use attribution may be incomplete.

Simulation source commit(s): `258a9b781059c41bdf07e6a094ed1a6f1a037246`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual is closing stock minus prior closing stock and traced net flow. Legacy censuses that predate provincial shipment holdings reconstruct the in-transit cargo change from dispatch and arrival events; censuses that include the cargo pool use it directly. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.
