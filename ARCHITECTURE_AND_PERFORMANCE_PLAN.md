# Call of Capital: Architecture, Performance & Shared-State Debugging Plan

**Status**: Completed & Verified (Living Execution Document)  
**Started**: 2026-10-25  
**Scope**: Codebase architecture review (`270` production `.py` files, `122,636` LOC), hot-loop performance optimization, causal-trace indexing overhaul, centralized shared-state mutation handler & debugging infrastructure, and structural de-duplication.

---

## 1. Executive Summary & Architectural Assessment

### 1.1 Architectural Strengths
1. **Clear Turn Pipeline ([`sim_engine.py:step_turn`](file:///Users/sli/Code/sim_engine.py#L26-L409))**:
   - Deterministic 9-stage macro/micro turn pipeline (Macro-Finance → Local Economy → Inter-Region Trade → Demographics → Sovereign Fiscal/Bond Market → Popular Resistance → Geopolitics → Innovation → Strict Stock-Flow Closure).
2. **Rigorous Conservation & Causal Accounting**:
   - Multi-currency conservation via [`forex.py`](file:///Users/sli/Code/forex.py), public account continuity via [`treasury_trace.py`](file:///Users/sli/Code/treasury_trace.py), bank balance-sheet continuity via [`bank_trace.py`](file:///Users/sli/Code/bank_trace.py), double-entry actor statements via [`economy/actor_accounts.py`](file:///Users/sli/Code/economy/actor_accounts.py), and compact causal event streams via [`run_trace.py`](file:///Users/sli/Code/run_trace.py).

### 1.2 Architectural Bottlenecks & Redundancies Identified
1. **Parallel Legacy vs. Modern Engines**:
   - [`econsim.py`](file:///Users/sli/Code/econsim.py) and [`econsim_trade_money.py`](file:///Users/sli/Code/econsim_trade_money.py) retain standalone single-region loops alongside the canonical [`micro/region/stepper.py`](file:///Users/sli/Code/micro/region/stepper.py) + [`region_market.py`](file:///Users/sli/Code/region_market.py) + [`region_production.py`](file:///Users/sli/Code/region_production.py) + [`region_labor.py`](file:///Users/sli/Code/region_labor.py) + [`region_finance.py`](file:///Users/sli/Code/region_finance.py) pipeline.
2. **Duplicated World-Builder Graph Passes**:
   - [`sim_world.py`](file:///Users/sli/Code/sim_world.py) and [`sim_world_voronoi.py`](file:///Users/sli/Code/sim_world_voronoi.py) duplicated ~240 lines of 4-pass trade-route topology logic (mountain pass unblocking, corridor scoring, degree-1 promotion, degree-cap enforcement, connected-component bridging, and ForexDesk initialization).
3. **God Objects (`Agent` & `Region`)**:
   - [`Agent`](file:///Users/sli/Code/agent.py) combines 9 entity types in a single class with ~120 `__slots__` plus a custom `__setattr__` / `_extra_attrs` fallback.
   - [`Region`](file:///Users/sli/Code/micro/region/core.py) mixes geography, institutions, and 60+ time-series lists.
4. **Scattered Shared-State Mutations & 4-Layer Manual Telemetry**:
   - `agent.cash += / -=`: **418** occurrences across **73** files (`+23` direct `.cash =` assignments).
   - `agent.inv_add / inv_set`: **142** occurrences across **38** files (`+25` direct `.inventory[...]` mutations).
   - `begin_public_change / finish_public_change`: **1,094** manual wrapper calls across **74** files.
   - `record_economic_event`: **97** calls across **34** files.
   - `emit / _emit`: **504** calls across **94** files.

---

## 2. Benchmark Results: Baseline vs. Post-Optimization

All benchmarks were measured with `cProfile` (`seed=42`, after 3 warm-up turns):

| Benchmark Workload | Baseline Turn Time | Optimized Turn Time | Speedup | Function Calls (Before → After) |
| :--- | ---: | ---: | ---: | ---: |
| **Untraced Nation Sim** (`sim_nation`, 6 tiles, ~1,338 agents, 25 turns) | `1,666.37 ms/turn` (`41.66s`) | **`827.57 ms/turn`** (`20.69s`) | **`2.01x faster`** (`-50.3%`) | `272.4M` → **`101.6M`** (`-62.7%`) |
| **Traced Nation Sim** (`sim_nation` + `RunTrace`, 6 tiles, 12 turns, 296.8k events) | `3,505.52 ms/turn` (`42.07s`) | **`1,796.39 ms/turn`** (`21.56s`) | **`1.95x faster`** (`-48.8%`) | `155.1M` → **`65.0M`** (`-58.1%`) |
| **Untraced Full World Sim** (`sim_world`, 81 hex tiles, 12 claimed, ~1,119 agents, 10 turns) | `1,497.98 ms/turn` (`14.98s`) | **`731.64 ms/turn`** (`7.32s`) | **`2.05x faster`** (`-51.2%`) | `101.2M` → **`32.5M`** (`-67.9%`) |

### Subsystem Breakdown (Untraced Nation Sim, 25 Turns)
| Hot Function / Subsystem | Baseline Cumulative Time | Optimized Cumulative Time | Improvement |
| :--- | ---: | ---: | ---: |
| [`RandomCache._refill`](file:///Users/sli/Code/random_cache.py#L25-L48) (`econsim_live.Live`) | `5.97s` (`300` refills of `200,000` floats) | **`0.00s`** (lazy refill on exhaustion) | **`-100%`** (`5.97s` saved) |
| [`alienation.step_tile_alienation`](file:///Users/sli/Code/alienation.py#L310-L420) | `6.24s` ($O(N^2)$ `a_species` + despair scans) | **`<0.35s`** (dropped out of top 20!) | **`17.8x faster`** (`~5.9s` saved) |
| [`capitalist_planner.plan_and_execute_elite`](file:///Users/sli/Code/economy/capitalist_planner.py#L1059) | `5.95s` (`3,834` luxury scans + unguarded trace dicts) | **`1.22s`** | **`4.89x faster`** (`4.73s` saved) |
| [`econsim_live.Live`](file:///Users/sli/Code/econsim_live.py#L94) | `5.40s` | **`1.64s`** | **`3.29x faster`** (`3.76s` saved) |
| [`actor_accounts.seal_turn`](file:///Users/sli/Code/economy/actor_accounts.py#L347) | `3.36s` | **`2.32s`** | **`1.45x faster`** (`1.04s` saved) |
| [`region_labor.calculate_labor_market_tightness`](file:///Users/sli/Code/region_labor.py#L138) | `1.28s` (`5,356` calls) | **`0.61s`** (`4,107` calls) | **`2.10x faster`** (`0.67s` saved) |
| [`trace_index.KnownEventIds.__contains__`](file:///Users/sli/Code/trace_index.py#L132) (Traced Sim) | `11.20s` (6 SQLite index rebuilds on 4,096-entry LRU miss) | **`<0.001s`** (`limit=262144`, zero cold misses) | **`>10,000x faster`** (`11.20s` saved) |
| `builtins.getattr` overhead | `6.08s` (`87.5M` calls) | **`2.73s`** (`33.7M` calls) | **`2.23x faster`** (`-61.5%` calls) |

---

## 3. Phased Execution Log & Completed Changes

### Phase 1: Reproducible Benchmark & Verification Harness
- [x] Profiled `sim_nation` (untraced & traced) and `sim_world` (untraced 81-tile hex world) with `cProfile`.
- [x] Identified why `test_scenario_playthroughs.py:test_every_declared_ending_has_a_player_decision_path` previously timed out at 180s (`audit_egypt_strategic_integration.py --case relief_payment --fiscal 0.0` was bottlenecked by the unoptimized turn loop).

### Phase 2: Hot-Loop Performance Optimizations
- [x] **2.1 Fixed `RandomCache` Refill Thrashing ([`random_cache.py`](file:///Users/sli/Code/random_cache.py#L25-L48))**:
  - `RandomCache.reset()` was called twice per tile per turn (`econsim_live.py:130` and `region_production.py:322`) and unconditionally regenerated `200,000` random floats (`60M` wasted `random.random()` calls over 25 turns).
  - Updated `reset(force=False)` to refill lazily only when `self._idx >= self._capacity` (or when `force=True`) and optimized `_refill()` with a list comprehension `[ _r() for _ in range(self._capacity) ]`.
- [x] **2.2 Eliminated $O(N^2)$ Agent Scans in [`alienation.py`](file:///Users/sli/Code/alienation.py#L15-L60) & [`agents/resistance/manager.py`](file:///Users/sli/Code/agents/resistance/manager.py#L130-L185)**:
  - Precomputed `precomputed_a_species` and `despair_candidates` once per tile in [`step_tile_alienation`](file:///Users/sli/Code/alienation.py#L360-L378) and passed them into `compute_agent_alienation` and `process_despair_spending`.
  - Pre-filtered `sympathetic_donors` once per revolt march in [`PopularResistanceManager._feed_revolt_participants`](file:///Users/sli/Code/agents/resistance/manager.py#L138-L185) instead of scanning `tile.agents` for every marching peasant.
- [x] **2.3 Eliminated Repeated Luxury & Market Scans in [`economy/capitalist_planner.py`](file:///Users/sli/Code/economy/capitalist_planner.py#L184-L285)**:
  - Pre-filtered `non_lords` in [`get_market_luxuries`](file:///Users/sli/Code/economy/capitalist_planner.py#L184-L212) and used direct `a.inventory[g_idx]` indexing.
  - Inverted the loops in [`check_new_market_items`](file:///Users/sli/Code/economy/capitalist_planner.py#L215-L246) so each good breaks immediately on the first agent holding `> 0` units.
  - Passed `_luxuries=luxuries` into [`calculate_shadow_price_cash`](file:///Users/sli/Code/economy/capitalist_planner.py#L249-L285) from `_plan_and_execute_elite` to eliminate the duplicate per-elite luxury scan.
  - Guarded trace-only diagnostic list/dict comprehensions (`sector_evaluations`, `input_inventory`, `liquidation_evaluations`, `buyer_checks`) behind `if trace_enabled:` in [`_plan_and_execute_elite`](file:///Users/sli/Code/economy/capitalist_planner.py#L1993-L2344).
- [x] **2.4 Optimized Labor Market Tightness & Cohort Filtering ([`region_labor.py`](file:///Users/sli/Code/region_labor.py#L138-L167), [`economy/transformation_graph.py`](file:///Users/sli/Code/economy/transformation_graph.py#L494-L514), [`economy/labor_mobility.py`](file:///Users/sli/Code/economy/labor_mobility.py#L335-L343))**:
  - Rewrote [`calculate_labor_market_tightness`](file:///Users/sli/Code/region_labor.py#L138-L167) to compute vacancies and job seekers in a single pass with direct slot reads (`a.birth_round` arithmetic instead of calling `getattr(a, 'age', None)` twice per agent).
  - Reordered [`_check_statute_prereqs`](file:///Users/sli/Code/economy/transformation_graph.py#L494-L514) to evaluate cheap boolean gates before calling `calculate_labor_market_tightness`.
  - Hoisted `worker_tightness = calculate_labor_market_tightness(region)` outside the `for firm in list(firms_with_vacancies):` loop in [`step_labor_cohort`](file:///Users/sli/Code/economy/labor_mobility.py#L335-L343).
- [x] **2.5 Fast `Agent` Inventory & Slot Access + [`economy/actor_accounts.py`](file:///Users/sli/Code/economy/actor_accounts.py) Optimization**:
  - Updated [`Agent.__setattr__`](file:///Users/sli/Code/agent.py#L276-L298), [`Agent.wealth`](file:///Users/sli/Code/agent.py#L324-L342), [`Agent.inv_get`](file:///Users/sli/Code/agent.py#L350-L363), [`Agent.inv_set`](file:///Users/sli/Code/agent.py#L364-L378), and [`Agent.inv_add`](file:///Users/sli/Code/agent.py#L379-L393) to index `self.inventory[good]` directly when `type(good) is Goods` (avoiding `13.3M` `Enum.__get__` descriptor calls).
  - Pre-indexed `bank_debt_by_agent`, `debt_by_debtor`, `plots_by_lord`, `plots_by_controller`, and `water_by_holder` once per tile in [`begin_turn`](file:///Users/sli/Code/economy/actor_accounts.py#L298-L345) and [`seal_turn`](file:///Users/sli/Code/economy/actor_accounts.py#L347-L410), and fixed [`_balance_sheet`](file:///Users/sli/Code/economy/actor_accounts.py#L598) to iterate over `own` instead of all tile `events`.
  - Short-circuited [`is_last_of_profession`](file:///Users/sli/Code/demographics_estate.py#L17-L30) as soon as `found > 1`.

### Phase 3: Causal Trace & Indexing Performance Overhaul
- [x] **3.1 Fixed `KnownEventIds` LRU Thrashing in [`trace_index.py`](file:///Users/sli/Code/trace_index.py#L132-L138)**:
  - Increased `KnownEventIds` default `limit` from `4096` to `262144` (~10 full turns of events) so `transporter.post` causal lookups hit in-memory $O(1)$ `OrderedDict` instead of rebuilding a 250k-row SQLite index mid-turn (`11.20s` → `<0.001s`).
- [x] **3.2 Fast Subject-Key Formatting in [`run_trace.py`](file:///Users/sli/Code/run_trace.py#L16-L25)**:
  - Added [`_subject_key`](file:///Users/sli/Code/run_trace.py#L16-L25) with a fast-path string formatter for standard 2-key `{'id': ..., 'type': ...}` subject dicts while preserving exact `json.dumps(subject, sort_keys=True)` string compatibility with [`bank_trace.py`](file:///Users/sli/Code/bank_trace.py#L108), [`treasury_trace.py`](file:///Users/sli/Code/treasury_trace.py#L170), and [`trace_snapshots.py`](file:///Users/sli/Code/trace_snapshots.py#L1329).

### Phase 4: Centralized Shared-State Mutation Handler & Debugging Infrastructure
- [x] **4.1 Created [`state_handler.py`](file:///Users/sli/Code/state_handler.py) ([`StateMutationHandler`](file:///Users/sli/Code/state_handler.py#L38-L355))**:
  - Implemented guarded, atomic mutations:
    - [`transfer_cash(payer, payee, amount, ...)`](file:///Users/sli/Code/state_handler.py#L197-L286): Atomically debits `payer` and credits `payee`, automatically wrapping `treasury_trace.begin_public_change` / `finish_public_change`, optional `actor_accounts.record`, conservation verification, and watchpoint notifications.
    - [`adjust_cash(actor, delta, ...)`](file:///Users/sli/Code/state_handler.py#L156-L195): Single-actor cash adjustment with `treasury_trace` and invariant guards.
    - [`transfer_good(giver, receiver, good, qty, ...)`](file:///Users/sli/Code/state_handler.py#L321-L368) and [`adjust_good(actor, good, delta, ...)`](file:///Users/sli/Code/state_handler.py#L292-L319): Guarded inventory mutations with conservation and negative-stock checks.
    - [`transfer_deposit(bank, payer, payee, amount, ...)`](file:///Users/sli/Code/state_handler.py#L374-L418): Atomic bank deposit transfer with `bank_trace` and `treasury_trace` hooks.
  - Built-in debugging & invariant infrastructure:
    - `strict_mode(allow_dead=False)` context manager enforcing finite numbers (`NaN`/`Inf` rejection), non-negative cash/inventory/deposit balances, zero conservation drift, and dead-agent mutation rejection.
    - `watch_agent(agent, cb)`, `watch_region(region, cb)`, `watch_all(cb)`, and `recent_mutations(agent_id=..., kind=...)` ring buffer.
  - Registered `'state_handler'` in [`simulation_checkpoint.py:SERVICE_PREFIXES`](file:///Users/sli/Code/simulation_checkpoint.py#L36-L38) so runtime debugging state never perturbs checkpoint state digests.
- [x] **4.2 Integrated `state_handler` into Core Economic Modules & Added Unit Tests**:
  - Wired [`region_finance.py:pay_wages`](file:///Users/sli/Code/region_finance.py#L62-L76), [`charity.py:Charity.collect_donations`](file:///Users/sli/Code/charity.py#L192-L250) & [`pay_for_food`](file:///Users/sli/Code/charity.py#L310-L318), and [`alienation.py:process_despair_spending`](file:///Users/sli/Code/alienation.py#L168-L202) & [`apply_mass_entertainment_pacifier`](file:///Users/sli/Code/alienation.py#L261-L276) to use `transfer_cash` / `adjust_cash`.
  - Created [`test_state_handler.py`](file:///Users/sli/Code/test_state_handler.py) covering cash conservation, `cap_at_payer_cash`, `strict_mode` (`NaN`, overdraft, negative inventory, dead-agent guards), `transfer_good`, `transfer_deposit`, watchpoints, and mutation history.

### Phase 5: Structural Code De-Duplication
- [x] **5.1 Consolidated World-Builder Trade Topology Passes into [`world_topology.py`](file:///Users/sli/Code/world_topology.py)**:
  - Extracted [`build_trade_network_topology`](file:///Users/sli/Code/world_topology.py#L14-L238) and [`connect_claimed_forex_and_trader_wealth`](file:///Users/sli/Code/world_topology.py#L241-L259) and refactored both [`sim_world.py`](file:///Users/sli/Code/sim_world.py#L255-L283) and [`sim_world_voronoi.py`](file:///Users/sli/Code/sim_world_voronoi.py#L368-L384) to delegate to `world_topology.py`, eliminating ~370 lines of duplicated graph-pass code while preserving 100% identical RNG and edge-selection semantics.
- [x] **5.2 Added Cohort Accessor Helpers on [`Region`](file:///Users/sli/Code/micro/region/core.py#L507-L530)**:
  - Added [`Region.living_households(include_traders=True)`](file:///Users/sli/Code/micro/region/core.py#L511-L521), [`Region.active_corporations()`](file:///Users/sli/Code/micro/region/core.py#L523-L525), and [`Region.labor_market_stats()`](file:///Users/sli/Code/micro/region/core.py#L527-L529).

---

## 4. How to Use `state_handler` for Debugging & Guarding

```python
from state_handler import (
    STATE_HANDLER,
    strict_mode,
    transfer_cash,
    watch_agent,
    watch_region,
    recent_mutations,
)

# 1. Watch all cash/inventory mutations on a specific agent or tile:
watch_agent(suspect_agent, lambda ev: print("AGENT MUTATION:", ev))
watch_region(region, lambda ev: print("TILE MUTATION:", ev))

# 2. Enable ring-buffer recording and strict runtime invariant guards:
STATE_HANDLER.history_enabled = True
with strict_mode(allow_dead=False):
    sim_engine.step_turn(turn, tiles, nations=nations)

# 3. Inspect recent mutations for any agent:
for entry in recent_mutations(agent_id=suspect_agent.id):
    print(entry)
```
