# Gameplay mechanism gates and modular turn pipeline

## Goal

Make each gameplay mechanism independently testable while preserving the current
full-game behavior by default. Put every *developer isolation flag* in one typed,
versioned configuration. A flag controls whether a mechanism runs; it is not a
government policy, player choice, map setting, or scenario state.

## Current boundaries

- `core/sim_engine.py` (438 lines) owns the world turn and calls province, local,
  trade, political, and military work.
- `micro/region/stepper.py` (162 lines after phase extraction) orders local work.
- `sim_server/sim_server.py` (about 2,000 lines after extraction) adds scenario hooks, bond settlement,
  traces, histories, and transport after the engine turn.
- `meso/province.py` runs shared institutions around each region's local turn.
- Legacy experiment switches for owner planning, career mobility, private
  technology adoption, food logistics, and independent input requests now read
  the central run config. `abundance_enabled`, `food_spoilage_enabled`, and
  `responsive_wages` remain owning-object model or policy inputs, with their
  corresponding central mechanism flag able to disable the work for an
  experiment. Policy state such as `ubi_enabled` stays on government objects.
- `sim_ring`, `sim_world`, and `sim_nation` call `step_turn` directly, so the
  config cannot live only on `SimServer`.

## Central configuration contract

Extend the existing `core/world_config.py`, which already owns the Call of
Capital topology and world settings. Add a frozen `GameplayFlags` value there
with named boolean fields, `FULL` defaults, named profiles, dependency
validation, and a stable serialized form/version. Do not create a separate
gameplay config module. There must be no second copy of a flag's default in a
caller's `getattr(..., default)`. Keep gameplay flags as a per-run value even
though the module's current topology setting is process-wide.

`commonweal/sim/config.py` configures the separate Commonweal simulator;
`economy/econsim_states.py` mixes legacy constants with mutable single-region
state. Neither is the source of flags for the authoritative Call of Capital
turn pipeline.

`SimServer` owns one resolved `GameplayFlags` value per run. Pass it to
`step_turn`, `Province.step`, and `Region.step_economy` explicitly. Direct
engine callers receive `FULL` unless they supply a config. Scenario overrides
are resolved by the same central builder before the first turn. Save the
resolved config in checkpoints and expose its profile, version, and enabled
flags in run metadata.
Do not mutate flags mid-turn or infer them from process-wide globals.

Provide `full`, `core`, and `isolate:<mechanism>` profiles. `isolate` starts
with the always-on kernel and enables the named mechanism plus its declared
dependencies. Print the resolved set so an experiment is reproducible. Reject
unknown flags and invalid combinations instead of silently enabling more work.

The always-on kernel is turn numbering, trace/ledger boundaries, route and
inventory bookkeeping needed to keep state valid, conservation checks, and
turn-aligned observations. It has no feature flags. A disabled mechanism must
have a documented neutral result (for example zero events and a zero-valued
history sample) and must not leave stale work for a later turn.

## Initial flag inventory

This is the first catalog to implement. Before each gate is wired, follow its
call graph and document both direct and indirect effects. One flag owns one
mechanism, even when that mechanism has several helper functions.

| Phase | Candidate flags | First gate boundary |
| --- | --- | --- |
| Strategy | `nation_ai`, `construction_projects` | `sim_engine.step_turn` |
| Food | `food_relief`, `food_spoilage`, `household_food` | `sim_engine`, `Province.step`, region stepper |
| Local resources | `land_rent`, `foraging`, `production`, `feudal_tribute`, `crop_credit` | region stepper |
| Local economy | `labor_market`, `elite_planning`, `career_mobility`, `workplace_resistance`, `local_market`, `wages`, `profits`, `taxation`, `abundance`, `independent_input_requests` | region stepper and owned helpers |
| Local society | `household_lifecycle`, `workhouse`, `alienation`, `pollution`, `disease`, `factions`, `unrest` | region stepper |
| Interregion | `regional_trade`, `forex`, `migration`, `frontier_claims`, `trade_epidemic_spread` | `sim_engine.step_turn` |
| National/world | `regime`, `military`, `wars`, `diplomacy`, `innovation`, `private_technology_adoption`, `popular_resistance`, `imperialism`, `sovereign_bonds` | engine or server post-turn |

Do not treat these names as a claim that all mechanisms are already enumerated.
The inventory pass must also inspect scenario after-hooks, wilderness stepping,
and module-internal periodic work, then add missing mechanisms to this one
catalog before calling coverage complete.

## Rollout, one mechanism at a time

1. **Inventory and baseline.** Record the full call graph and ownership of
   every state-changing step. Capture fixed-seed `FULL` state digests and
   ledger/trace summaries for normal, Voronoi, hex, and scenario runs.
2. **Introduce config without changing behavior.** Add the central catalog,
   explicit config propagation, CLI/API run selection, and checkpoint metadata.
   `FULL` must be equivalent to the pre-gate baseline.
3. **Gate isolated effects first.** Add one gate per change for disease,
   pollution, alienation, workhouse, factions, unrest, innovation, imperialism,
   and bonds. Define the disabled result and verify it before moving on.
4. **Gate coupled world flows.** Add migration, claims, diplomacy, wars,
   military, forex, and trade. Resolve in-flight cargo, orders, and currency
   records explicitly when a feature is off.
5. **Gate coupled local flows.** Add food, labor, markets, production, wages,
   taxes, and lifecycle. Declare prerequisites and neutral history samples;
   split large local functions into ordered phase modules as each gate lands.
6. **Migrate legacy switches.** Replace region/nation isolation attributes
   with central config lookups. Keep true game state and player policy on the
   owning objects. Move scenario overrides into the central profile builder.
7. **Finish modularization.** Extract server turn orchestration from transport
   and serialization, and extract engine/local phases by responsibility. Keep
   a short orchestrator that visibly lists phase order and gate checks.

Each change contains one mechanism (or a tightly coupled dependency pair),
its disabled-state contract, and its focused checks. Avoid a single large
rewrite of `step_turn` or the region stepper.

## Acceptance for each gate

- `FULL` produces the same state, events, and accounting as before that gate.
- `core` and `isolate:<mechanism>` advance turns without exceptions, stale
  pending work, missing chart samples, or unexplained ledger shifts.
- The target's own state/events change when enabled; with it disabled, its
  state-changing entry points do not run. Declared dependencies are visible.
- Saving/restoring a checkpoint keeps the exact resolved flags and deterministic
  continuation. Normal, web, desktop, CLI, and scenario entry points agree.
- Mechanism tests use fixed seeds and assert effects and invariants; one
  all-enabled regression run guards default gameplay.

## Implementation status

The first slice is wired through `core/world_config.py` and passed per run
through `SimServer`, `step_turn`, provinces, regions, and the lifecycle context.
Both CLI and web server accept repeatable `--disable-mechanism NAME`; the
resolved flags are included in serialized world state. The currently wired
switches are the fields of `GameplayFlags` in the central config. Local phase
gates preserve one history sample per turn when disabled. Disabling `disease`
also disables `trade_epidemic_spread`, and the CLI prints the resolved set.
Construction project stepping is now separate from private technology adoption
and operational building staffing; existing military, diplomatic, and bond
intents are rejected when their mechanism is disabled.
The next set adds gates for elite planning, career mobility, workplace
resistance, foraging, tribute, abundance, national food logistics, and
independent input requests. Food spoilage remains in the coupled food phase.
The forex gate freezes bilateral quotes, keeps one quote-history sample per
turn, and skips interbank cycling and automatic wallet conversion while
leaving trade settlement available at the frozen quote.
The regional trade gate freezes route cargo and parked goods, stops new export
dispatch and bilateral/wilderness settlement, and still records zero-valued
turn trade totals. Forex can remain enabled independently.
Bilateral settlement and source-valued export rows now live in
`meso/trade_flow.py`, leaving the world turn orchestrator shorter.
The cash land-rent gate prevents assessment and payment and freezes any
pre-existing rent claim balance while retaining its arrears reading.
Provincial food relief has its own gate. Disabling it leaves dispatched food
shipments in place and prevents arrival or new levy and dispatch; national
coordination remains governed by the existing national logistics flag.
Household food sharing has its own gate around proportional meal allocation.
The turn still records household food need when sharing is disabled.
The taxation gate skips fixed and income tax assessment while preserving public
debt service, the fiscal gap sample, and deficit borrowing.
The profits gate skips owner dividends, salaries, loan repayment, and bailout
flows as one mechanism; firms retain their cash for subsequent turns.
The household lifecycle gate skips births and mortality while preserving
turn-aligned death counts and the rest of the demographic pass.
The local market gate skips both input clearing and post-payroll food purchases;
regional trade remains controlled separately.
The wages gate freezes payroll, arrears settlement, and scrip redemption while
extending any pending strike review window so the review waits for wages.
The production gate skips crop input commitment, worker allocations to crops,
machinery depreciation, and all crop, pastoral, and industrial output. It emits
zero output history samples, clears production receipts and emissions for the
turn, and leaves scheduled granary release active as a food logistics effect.
The labor market gate stops firm creation and wage quote changes while leaving
existing employment, solvency handling, and the career mobility gate intact.
Region lifecycle stepping and trader transitions now live in
`micro/region/lifecycle.py`; the stepper retains its existing `live()` entry
point and delegates to that module.
Population and economy telemetry sampling now lives in
`micro/region/telemetry.py`, with compatibility entry points retained in the
stepper.
The crop-credit gate prevents advances, offtake delivery, lien seizure, and
cash repayment of advance claims. Crop-share tenancy remains active as its
own mechanism.
Crop-share tenancy now has a separate gate for new agreements and harvest
settlement, so it can be tested independently of advances and liens.
Natural food spoilage now has a central gate. When disabled, it leaves food
stocks and fractional loss remainders untouched while food preparation, seed
reservations, and physical storage-capacity overflow still run.

The central `GameplayFlags` catalog in `core/world_config.py` is versioned and
is passed through `SimServer`, `step_turn`, provinces, regions, and direct
engine callers. `full`, `core`, and `isolate:<mechanism>` profiles resolve
before world creation; dependencies are explicit, invalid flags are rejected,
and run metadata plus checkpoints retain the exact profile and flag set. Both
CLI entry points accept profiles and repeatable `--disable-mechanism` options.
Scenario defaults are centralized, while explicitly supplied configs remain
authoritative. Tests cover one-turn core and wilderness isolation, dependency
resolution, and individual disabled entry points.

All catalogued world, national, regional, and local mechanisms now have gate
checks. This includes scenario progression and wilderness, which were added by
the inventory pass. Disabled contracts retain accounting boundaries and
turn-aligned histories; trade and forex can be varied independently; natural
food spoilage, crop credit, crop-share tenancy, food relief, and wage reviews
are separate mechanisms. Legacy isolation attributes for owner planning,
career mobility, private technology adoption, and regional/national logistics
are no longer secondary mechanism gates. The existing world-setting and policy
inputs for abundance, spoilage, and responsive wages remain, and central flags
can disable those mechanisms.

Completed extractions include bilateral settlement and export rows in
`meso/trade_flow.py`, region lifecycle stepping in
`micro/region/lifecycle.py`, region telemetry in `micro/region/telemetry.py`,
tile/plot serialization in `sim_server/serialization.py`, and server-level
turn work in `sim_server/turn_pipeline.py`. `SimServer.step()` now delegates to
the pipeline module; scenario hooks, claims, bond settlement, telemetry, and
event publication retain their previous order. Regional turn phases now live
in `micro/region/opening_phase.py`, `production_phase.py`, `society_phase.py`,
`health_phase.py`, and `closeout_phase.py`; `step_economy()` retains the order
and central gate context. Compatibility entry points remain where callers
depend on them.

Focused checks pass for gameplay flags, economic policy response, food economy
v2, technology adoption, elite planning, tile parity, the single-tile web
endpoint, M5 diplomacy, bonds, desktop renderer compatibility, and a canal
endpoint, M5 diplomacy, bonds, desktop renderer compatibility, and a canal
scenario playthrough. All five checkpoint continuation tests pass after
`core/simulation_semantics.py` learned to encode Python slot descriptors used
by the current workspace state. A direct checkpoint round trip also confirms
the saved profile, flag version, and exact resolved values.

Three-turn fixed-seed aggregate state digests match clean `main` and feature
archives for both ordinary topologies and both authored rivalry scenarios; the
recorded hashes are in `planning/reports/gameplay_gates_acceptance_20261111.md`.
They cover per-tile population, GDP, cash, bank equity, inventories, prices,
trade, foraging and unrest; nation treasury and population; and currency
violations. The 15-path scenario ending matrix was not completed because its
subprocess run exceeded practical runtime. These comparisons provide a
cross-topology default-equivalence check over the listed aggregate state, not a
byte-for-byte digest of every object in the world.
