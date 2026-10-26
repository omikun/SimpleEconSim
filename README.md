# Call of Capital / SimpleEconSim

A multi-scale political economy, geopolitical rivalry, and historical crisis simulator with causal trace verification and interactive desktop/web clients.

---

## Repository Structure

```text
├── core/                 # Central simulation loop, world generation, StateMutationHandler, topology indices
├── micro/                # Tile-level microeconomics (markets, production, labor, finance, tenure, disease)
│   └── region/           # Region class, economic stepper, and cash conservation auditing
├── meso/                 # Inter-regional logistics, provinces, foreign exchange (Forex), and migration
├── macro/                # National governance, diplomacy, military, sovereign bonds, and imperialism
│   └── imperialism/      # Core-periphery receivership, blockades, and gunboat coercion
├── agents/               # Agent entities, social classes, and popular resistance / communes
│   └── resistance/       # Anti-enclosure revolts, strikes, and barricades
├── economy/              # Capitalist planning, transformation graphs, finance bills, triangular trade
├── terrain/              # Procedural elevation, Amit Patel polygonal maps, hydraulic erosion, hex geometry
├── scenarios/            # Declarative & historical campaign engine (Egypt 1877, Empire of Cotton, Rivalry)
├── trace/                # Causal trace engine, O(1) TraceIndex, metric catalog, and contract verification
├── client/               # Client frontends
│   ├── desktop/          # Pygame desktop worldview UI, panels, HUD, inspect drawers, tooltips, charts
│   ├── headless/         # Headless game client for automated testing and batch runs
│   └── web/              # Web static client mount
├── sim_server/           # REST/WebSocket simulation server and command protocol
├── render_engine/        # GPU ModernGL BRDF micropolygon pipeline and camera utilities
├── tests/                # Comprehensive unit, causal trace, and scenario integration test suite (200 files)
├── scripts/              # Campaign audit runners, map generator comparisons, and utility scripts
├── benchmarks/           # Simulation performance and career/supply mobility benchmarks
├── docs/                 # Game Design Document (gdd.md), feature specifications, and mechanics guides
├── planning/             # Architectural plans, roadmaps, and coverage baselines
│   ├── audits/           # Historical campaign audit reports
│   └── coverage/         # Static AST financial writer baselines
└── outputs/              # Generated diagnostic plots, profiling outputs, and logs (git-ignored)
```

---

## Quick Start

### 1. Run Desktop Worldview Client
```bash
./venv/bin/python worldview.py
```

### 2. Run Web Server & Browser Client
```bash
./venv/bin/python -m sim_server.web_server
```

### 3. Run Unit & Causal Trace Tests
Run specific test modules:
```bash
./venv/bin/python -m unittest tests/test_state_handler.py tests/test_trace_index.py tests/test_causal_gap_inventory.py
```
Or discover all tests in [`tests/`](file:///Users/sli/Code/tests):
```bash
./venv/bin/python -m unittest discover -s tests
```

---

## Key Architectural Subsystems

- **Centralized State Mutation & Guarding ([`core/state_handler.py`](file:///Users/sli/Code/core/state_handler.py))**:
  Provides [`StateMutationHandler`](file:///Users/sli/Code/core/state_handler.py#L46-L426) (`state_handler`) for atomic, conservation-checked mutations of agent cash (`transfer_cash`, `adjust_cash`), inventory (`transfer_inventory`, `adjust_inventory`), and bank deposits (`transfer_deposit`), with watchpoints, NaN/Inf guards, and causal trace hooks.
- **Precomputed World Topology ([`core/world_topology.py`](file:///Users/sli/Code/core/world_topology.py))**:
  Builds `O(1)` spatial neighbor and nation/province tile indices (`build_neighbor_index`, `build_nation_tile_index`) used across regional logistics, diplomacy, and world stepping.
- **Indexed Causal Trace Engine ([`trace/run_trace.py`](file:///Users/sli/Code/trace/run_trace.py), [`trace/trace_index.py`](file:///Users/sli/Code/trace/trace_index.py))**:
  Records every state mutation and decision into a compact binary trace (`.ctr`) with an incremental in-memory [`TraceIndex`](file:///Users/sli/Code/trace/trace_index.py#L65-L345) for `O(1)` event-ID, turn, metric, and subject lookups.
