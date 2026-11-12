# Gameplay gates acceptance spot check

## Default behavior comparison

Compared clean Git archives of `main` at `154a7d2` and the completed
gameplay-gates feature at `1cad16e`. Each process reset Python and NumPy RNGs
to seed `4243`, created a server with seed, terrain seed, and nation seed
`4243`, disabled causal tracing, and advanced three turns with default gameplay
flags. The scenario profiles used their normal scenario defaults.

The SHA-256 digest is over a sorted JSON summary containing each tile's
population, nominal GDP, total cash, bank equity, per-good inventory and price,
exports, imports, foraged food, and unrest; each nation's treasury and
population; and the turn, topology, scenario identifier, and currency
violations.

| Run | Tiles | Nations | Violations | Matching digest |
| --- | ---: | ---: | ---: | --- |
| Hex, ordinary world | 81 | 3 | 0 | `0380e973163ce2b47b1c5426235a84068a667d9fd58f5de7ed7564c7449e6ac8` |
| Voronoi, ordinary world | 80 | 3 | 0 | `43d8db34df3cf2507df0cdce1d5d709e002dc814d2102461ec025aaad7c738ce` |
| Labor frontier rivalry | 4 | 2 | 0 | `35c16bc5a9cb1d596d82f26891dc53e833d9b6d98138e9e41e60dba3441f3e66` |
| Supply rivalry | 2 | 2 | 0 | `aae3b5c714e5200ea6a5c005c0868a8244727811c8d19f2a2873f4e945750a00` |

Each digest was identical between the two revisions. This checks the listed
aggregate state after three turns; it is not a byte-for-byte digest of every
object in the world.

## Regression checks

- 98 tests passed across gameplay flags, economic policy response, food economy
  v2, technology adoption, and elite planning.
- 26 web client parity and single-tile endpoint tests passed.
- 37 M5 diplomacy, sovereign bond, bond announcement, and desktop renderer
  tests passed, with zero LEAK and zero SUPPLY SHIFT in the M5 acceptance run.
- All five checkpoint continuation tests passed after the current workspace's
  semantic-state helper was extended to encode Python slot descriptors. After
  the local phase split, the deterministic continuation test passed again on
  its own.
- The profession-population trace test passed after restoring its compatibility
  entry point. The full 39-test run-trace module has the same three existing
  failures on clean `main` and the feature: one `main_work` `KeyError` and two
  expected event-kind mismatches.
- The first canal scenario playthrough passed. The broader 15-path ending
  matrix was not completed because its subprocess run exceeded practical
  runtime.
