# Cotton/cloth aggregate stock-flow audit

This bounded audit compares consecutive whole-world stock censuses with
traced production, recipe input use and household non-food consumption.
Marketplace, aid, other internal transfers and route events are counted
as turnover, not net flow: both sides and route cargo are inside the
census boundary. This does not prove every possible stock writer is
instrumented, and does not cover food, wood, or goods beyond cotton and
cloth.

| Seed | Shock | Arm | Cotton balanced | Cotton max residual | Cloth balanced | Cloth max residual | Issues |
|---:|---|---|---:|---:|---:|---:|---:|
| 812 | cotton supply | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 812 | cotton supply | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 812 | mill cotton demand | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 812 | mill cotton demand | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 813 | cotton supply | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 813 | cotton supply | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 813 | mill cotton demand | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 813 | mill cotton demand | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 814 | cotton supply | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 814 | cotton supply | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 814 | mill cotton demand | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 814 | mill cotton demand | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 815 | cotton supply | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 815 | cotton supply | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 815 | mill cotton demand | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 815 | mill cotton demand | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 816 | cotton supply | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 816 | cotton supply | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 816 | mill cotton demand | control | 19/19 | 0.0 | 19/19 | 0.0 | 0 |
| 816 | mill cotton demand | treatment | 19/19 | 0.0 | 19/19 | 0.0 | 0 |

Simulation source commit(s): `9915c7f4d5aaf8b10d35f0b80fc73253fab9b1de`.
Each run excludes turn 1 because no pre-turn-1 stock census exists.
Per-turn details and trace paths are in the JSON sidecar.

The residual equation is `closing stock - prior closing stock - traced production + traced recipe input use + traced household non-food consumption`. A zero aggregate residual supports the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.
