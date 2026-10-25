# Default-game food stock-flow follow-up

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use, food inflows and consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented. Food includes public stores, regional granaries and one
per-region civilian meal total each turn; army rations are separate.

| Seed | Experiment | Arm | Balanced intervals | Issues |
|---:|---|---|---:|---:|
| 4242 | wood_supply_reduction | control | 3/19 | 0 |

| Good | Balanced intervals | Total intervals | Max absolute residual |
|---|---:|---:|---:|
| food | 3 | 19 | 472 |

Complete stock-flow closure: 0/1 runs. Structural or coverage issues: 0. A run can have no structural issues and still fail because one or more good-stock intervals do not balance.

This selected-goods view is a diagnostic screen. A nonzero residual identifies a stock-flow gap; zero residuals can still hide offsetting unsupported flows.

Simulation source commit(s): `769a9aedd6c9fb4f39aed001b3ef26a5e0224333`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual is closing stock minus prior closing stock and traced net flow. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.


On clean source `769a9ae`, the emergency-food queue totals zero at all 20 checkpoints in this control. Adding it to the census therefore does not change the turn-3 balance: stock rises by 1,585 against +1,745 traced net flow, leaving the same -160 residual. Food closes in 3/19 intervals, with a maximum absolute residual of 472 units.

Coverage note: this is one seed-4242 wood-supply-control baseline arm. It rules out a nonzero emergency-food queue as the cause of the observed gap in this arm only; other lifecycle and trade/storage stock writers remain under investigation, and this is not a cross-seed or treatment-arm closure result.
