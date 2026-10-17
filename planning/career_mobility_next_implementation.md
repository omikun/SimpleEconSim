# Career mobility: next implementation plan

Date: 2026-10-17

## Goal and current baseline

Make population and labor flows explainable, then give residents credible
choices among subsistence, wage work, and other livelihoods. The player should
see how land and labor policy changes food security, profits, unrest, and rival
capacity. Do not tune a global switch quota to manufacture a desired career
distribution.

The [game time rule](game_time_design.md) is fixed: **one turn is one agent
year** for age, occupation tenure, contracts, and demographic decisions;
**ten turns form one seasonal crop cycle**. A 50-turn benchmark therefore spans
50 agent years and five crop cycles. Rates of adult occupation change use
adult agent-years as their denominator. Seasonal work uses a bounded share of
an agent turn; it does not create a second full job or age agents differently.

At commit `446084d`, the seed-777 default three-nation 50-turn run reports
adult occupation changes of 1.52% / 1.21% / 1.50% per agent year and ending
adult food-career shares of 77.7% / 90.4% / 86.0% for the United States /
China / Japan. The United States has nine reported starvation deaths.
`benchmark_career_mobility.py` also reports 224 / 126 / 219 people missing
from successive snapshots in those nations. Those **exits are not death
counts**: `metric_catalog.py` currently says `people.deaths` covers
`demographics_estate.handle_death` but not violent deaths. Preserve these
numbers as an initial reference, then establish a traceable baseline before
interpreting rate changes.

## Rules that apply to every phase

1. Keep each person identified by stable `Agent.id`. Distinguish residents
   from corporate and government entity agents; record a human becoming a
   different role instead of silently dropping that ID. Never infer death
   merely from absence in one tile or one snapshot.
2. Preserve conservation of food, cash, goods, and named people. An
   alternative livelihood must use real access, inputs, funded wages, and a
   buyer or a subsistence destination. Do not mint initial food when someone
   changes occupation or becomes a trader.
3. Emit the causal event at the mutation site into the existing compact
   `.ctr` trace. Snapshots and UI summaries aggregate those events. Use one
   canonical operation per state change and avoid duplicate events when two
   callers touch the same person.
4. Treat occupation, employer, activity, residence, and legal constraint as
   separate axes. A forced labor placement is not a voluntary career choice.
5. Keep deterministic seed-777 comparisons and add small focused tests for
   each invariant. Run broader scenarios only after a concrete gate passes.
   Commit after each completed phase so a regression can be located.

## Phase A — Reconcile people before changing behavior

**Primary files:** `benchmark_career_mobility.py`, `trace_snapshots.py`,
`metric_catalog.py`, `demographics_estate.py`, `army.py`,
`agents/resistance/manager.py`, `migration.py`, `government.py`,
`scenario_political_economy.py`, `micro/region/stepper.py`, `run_trace.py`,
relevant tests.

1. Define two populations in code and in benchmark output: all **living
   human persons** (including children, traders, workers, soldiers, and
   temporarily displaced people), and **eligible adults** (age 14+ for work;
   report a separate employed adult denominator for comparison with labor
   surveys). Corporate and government entity agents are never persons in the
   numerator. A role change must keep the person's identity or carry an
   explicit role-conversion event.
2. For every turn, take a full-world ID snapshot before and after stepping.
   Include alive status, tile, nation, role flags, native-child status, age,
   primary occupation if present, and employer ID. Reject duplicate living
   IDs and report a small list of IDs for every unexplained mismatch. Do not
   disable trace collection in the diagnostic run; retain a faster no-trace
   mode for repeated balance runs.
3. Build a person-flow ledger with `birth`, `immigration`, `death` by cause,
   `migration` (origin and destination), `role_conversion`, and `unknown`.
   Reconcile at world, nation, and tile levels:

   `end = start + births + arrivals - deaths - departures + conversions_in - conversions_out`

   World migration must net to zero. Becoming an adult is a cohort entry,
   not a birth. Same-turn births and deaths need explicit events even if an
   end-of-turn snapshot never sees that person alive. `unknown` is an audit
   failure, not an allowed final category.
4. Audit every removal and `alive=False` path. Start with demographic death,
   battlefield casualty and enlisted movement in `army.py`, deaths in
   `agents/resistance/manager.py`, ordinary migration, scenario migration,
   and any firm/government role conversion. Trace the person ID, cause, turn,
   origin tile/nation, and destination where relevant. Ensure *all* death
   routes update the common death count once. Keep infant mortality attempts
   that never created an `Agent` separate from deaths of registered persons.
5. Update the compact trace reader/report so one can ask “where did person ID
   X go?” and “which event explains this tile's population delta?” Include
   this answer in benchmark diagnostics. Report occupation and employer
   changes only among comparable eligible adults; report child-to-adult entry
   separately.

**Tests and gate:** synthetic birth, same-turn infant death, migration,
military transfer, combat death, protest death, and role conversion each
reconcile exactly. The seed-777 50-turn default game has zero duplicate IDs
and zero unexplained person flows at all three levels. The ledger's death
count agrees with all registered-person death events, including violence.
Only then use the benchmark for calibration. **Commit A.**

**Phase A implementation note (2026-10-17):** The benchmark now observes all
world tiles, including wilderness, and distinguishes migration, death, birth,
and person/entity role conversion. Birth and death counters audit same-turn
events. Demographic, combat, and political deaths share an idempotent person
death record. `trace_report.py --person-id ID` retrieves named events from a
compact trace. The seed-777 50-turn fast run reports zero unknown exits and
zero unmatched birth/death events; a two-turn traced run verified its compact
checkpoints. Person counts are also sampled as `people.residents`, distinct
from legacy agent-count-oriented `people.population`. Two sequential 50-turn
seed-777 runs with fixed `PYTHONHASHSEED=0` and `MPLCONFIGDIR` produced identical
benchmark JSON and zero ledger failures.

## Phase B — Separate occupation from employer and temporary activity

**Primary files:** `agent.py`, `labor_choice.py`, `labor_contract.py`,
`economy/labor_mobility.py`, `demographics_career.py`, `region_labor.py`,
`region_logistics.py`, `buildings.py`, `army.py`, `migration.py`,
`metric_catalog.py`, tests.

1. Add a canonical `primary_livelihood` for human adults and a start turn for
   its current episode. Children have no adult primary livelihood until
   entry; their inherited `output` label is only a prospective household
   skill. Keep `output` for production compatibility during migration, but
   do not use it alone to count permanent career changes. Derive employment
   status from employer/contract/trader/military/workhouse state where
   possible, rather than storing another field that can drift.
2. Implement a single permanent occupation transition operation. It checks
   a real change, records old/new livelihood, voluntary or forced reason,
   access/skill preconditions, retained experience, and turn. It updates
   tenure once and emits exactly one `labor.occupation_change` event. No-op
   transitions leave tenure unchanged. Let same-sector hiring change the job
   spell without changing livelihood.
3. Route hire, quit, layoff, firm closure, building assignment, apprenticeship,
   trader entry/exit, migration, military service, and workhouse placement
   through explicit **job or status** transitions. A trader or soldier can
   suspend a prior trade and return to it; changing status alone must not
   relabel the person a lifelong food producer. Record coercion or debt-bound
   restrictions in the reason and eligibility decision.
4. Represent the first temporary activity narrowly: commons foraging or
   household craft for an eligible adult without a paid shift. Record hours or
   a share of the turn and its actual food/goods output. The sum of paid,
   independent, and temporary work allocation cannot exceed the turn's
   available work time. Keep tenancy/sharecropping as access and contractual
   status, distinct from payroll employment. Expand sidelines only after the
   first one balances.
5. Update the benchmark and trace metrics to count adult occupation entries,
   occupation changes, employer changes, unemployment spells, trader/military
   spells, and temporary work separately. Compare before/after rosters and
   contracts for every firm.

**Tests and gate:** same-trade hiring and employer changes preserve occupation
tenure; an actual career move changes it once; forced placement is labeled;
trader and military round trips restore prior trade where feasible; a
temporary activity cannot duplicate a full day's output; firm rosters,
contracts, goods, and cash reconcile. Run the Phase A person ledger after
these changes and require zero unexplained flows. **Commit B.**

**Phase B implementation note (2026-10-17):** Human agents now hold a primary
livelihood and episode start. Career transitions change that field once;
employment, trading, enlistment, and workhouse custody emit separate status
events. Trader entry no longer creates food, and apprenticeship grants no
longer top up food without a transfer. Commons foraging records food and a
bounded turn share, which reduces independent production opportunity. The
50-turn seed-777 ledger reconciles with zero unknown flows and validates every
firm roster each turn. Focused livelihood tests and the labor frontier scenario
suite pass. This phase establishes status accounting; the feasible opportunity
set and strategic balance are Phase C and D work.

## Phase C — Give agents feasible livelihood choices

**Primary files:** `economy/labor_mobility.py`, `labor_choice.py`,
`livelihood_access.py`, `region_market.py`, `region_production.py`,
`region_labor.py`, `government.py`, `food_security.py`, tests.

1. Replace the food/wood/furniture-only independent-return gate with
   activity-specific opportunities. A candidate must name its reachable
   plot or commons right, tool/skill source, input stock or affordable
   purchase, saleable output, buyer or observed local demand, and work time.
   Start with cultivation, wood, wool/cotton where terrain permits, furniture,
   and cloth piecework or factory employment. Do not unlock every good at
   once. Keep each route's productivity and costs distinct.
2. Score actual options for **staying**, a bounded sideline, tenancy or
   independent production, funded local wage offers, apprenticeship, and
   reachable migration. Score expected food for the worker and dependents,
   take-home cash after rent/tax/debt, input and travel costs, and job
   security over a short horizon. Use observed sales and finite demand;
   `price × hypothetical production` is not realized income. An employer
   must fund payroll and inputs; a migrant needs a reachable destination.
3. Respond to named shocks: loss of access, eviction, firm closure, sustained
   wage advantage, demand collapse, harvest failure, and youth entry.
   Temporary hunger can favor household sharing, relief, stored food, or
   foraging without instant retraining. Acute dispossession removes waiting
   time only when a feasible destination exists. Remove the rule that a
   hungry food-labeled resident must remain farming even when they have no
   land or effective harvest.
4. Allocate scarce opportunities once per turn. Vacancies, plots, tools,
   credit, training positions, and buyers have finite capacity. Evaluate
   offers in a stable order so a high-wage firm rejecting a worker does not
   hide an affordable lower-wage offer. Record rejected options and their
   reason in a compact decision trace, with bounded size per person/turn.
5. Recheck the child-dependent food budget and U.S. starvation cases. Keep
   parent food transfers and public aid conserved. Diagnose whether losses
   come from harvests, market access, household distribution, or policy
   before changing yields or death probabilities.

**Tests and gate:** protected commons supports independent subsistence;
enclosure plus a funded vacancy can produce wage entry; a dispossessed worker
without a feasible job remains unemployed/eligible for relief rather than
magically producing food; a firm closure creates an observable job loss;
one-turn price noise does not erase an established occupation. A good with
no buyer does not attract mass entry. The Phase A ledger and Phase B rosters
still reconcile. **Commit C.**

## Phase D — Validate strategy and show causes to the player

**Primary files:** `benchmark_career_mobility.py`, `trace_report.py`,
`trace_snapshots.py`, `sim_server/sim_server.py`, `web_client/client.js`,
`worldview_labor_ui.py`, scenario and integration tests.

1. Run the default three nations for 50 turns with seed 777 and at least two
   additional fixed seeds. Pair runs under commons protection, enclosure,
   cash tax, better wages, a firm closure, harvest failure, and food relief.
   Archive machine-readable parameters, commit SHA, and summary results in
   ignored `tmp/analysis/` output. Do not make test assertions from one
   stochastic seed's exact GDP or population.
2. Report adult occupation and employer transition matrices, reversals,
   youth entry, forced vs voluntary moves, status/temporary spells, migration,
   deaths by cause, adult food-producing time, calories, goods prices, real
   wages after obligations, firm margins, GDP, unrest, and rival fiscal and
   military capacity. Pair every aggregate with trace event IDs or a known
   formula; explain unexplained outcomes rather than smoothing them away.
3. Show the player the same causes in desktop and web views: people who kept
   subsistence access, took a funded job, entered tenancy, migrated, or were
   left without work, alongside changes in household food, wages, profits,
   unrest, and rival power. Distinguish a permanent career change from a job
   or seasonal activity. The detail view should expose named reasons without
   flooding the main screen with every agent event.
4. Tune only mechanisms with demonstrated failure: unreachable trades,
   missing buyers, blocked vacancies, non-conserved food, or policy that
   never changes a meaningful decision. Use the historical sources in
   [the follow-up plan](career_mobility_followup_plan.md) as shape checks,
   not as a universal annual quota. Compare like denominators and retain
   the one-agent-year-per-turn clock.
5. Check corporation and nation AI decisions in the paired runs. A firm under
   profit pressure may seek cheaper labor only through a funded offer or an
   enforceable institution with a visible cost. A nation should weigh the
   resulting production and rival strength against food security, unrest,
   policing, and fiscal cost. Log the alternatives considered and the reason
   for the chosen action, so a result can be explained without guessing from
   the final occupation mix.

**Acceptance:** the player has at least two viable strategic paths under
matched seeds: protect subsistence with lower labor supply and different
growth, or expand wage production with visible food/security and unrest
costs. Rival competition makes the choice consequential. Avoid mechanical
convergence to 80%+ adult food careers, but do not force a target share by
arbitrary caps. The traced run explains population, prices, mobility, and
deaths; both clients present matching summaries. Neither path should provide
free food, labor, enforcement, or military strength. **Commit D.**

## Execution order

Implement A before B, B before C, and C before D. If a phase's gate fails,
repair the cause inside that phase before proceeding. Do not combine a
population-accounting repair with a career-choice tuning change in the same
commit. Keep the current first-slice commit as the comparison point.
