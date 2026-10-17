# Career mobility after the first stabilization pass

Date: 2026-10-16

## Decision

Keep the recent reduction in rapid career changes, but rebuild the next pass
around **livelihoods and job spells**. The [game time design](game_time_design.md)
sets one agent year per turn while seasonal production cycles every ten turns.
A resident can work
for a different employer, forage in the off-season, or take a temporary
hauling job without permanently changing their primary occupation. Changing
from a cultivator to a joiner should normally require a credible opportunity,
skills and tools, and time. Losing land or a job can force a much faster
change, provided an executable destination exists. The game should show these
flows as consequences of player and AI policy, not suppress them to meet a
single global switch rate.

## Historical anchors and limits

- **One turn is one year for an agent**: age, career tenure, and an annual
  occupational transition rate advance once per turn. Seasons use a separate
  ten-turn cycle (`region_production.py`, `sim_server/sim_server.py`). An agent
  ages ten years during one complete seasonal cycle. Do not convert annual
  labor rates using the seasonal cycle length.
- The U.S. Census/BLS reported **8.7% of workers changed occupation from
  January 1972 to January 1973**. Its report says movement was more common
  between related occupations and less common among occupations with invested
  capital or clientele, including farmers and proprietors. This is a modern
  comparator, not a measured nineteenth-century rate or a target for all game
  residents. [Census Special Labor Force Report 176](https://www.census.gov/library/publications/1975/demo/bls-slfr-176.html).
- BLS reported occupational mobility declining with age in 2003–04, from
  27.1% among employed 16–19 year olds to 1.6% among those 65 or older. Its
  denominator includes people employed at both observations. These figures
  cannot be compared to switches divided by **all** game residents, which
  includes children, traders and the non-employed. [BLS, Occupational mobility
  and age](https://www.bls.gov/opub/ted/2006/jan/wk1/art02.htm).
- Historical records reveal **direction and institutions** better than a
  universal annual hazard. Linked 1851–1881 British censuses identify
  migration to towns as a route to occupational advancement, but the 30-year
  observation gap cannot show how often people changed work in between.
  [Long, linked-census study](https://www.cambridge.org/core/journals/journal-of-economic-history/article/abs/ruralurban-migration-and-socioeconomic-mobility-in-victorian-britain/E6E208B771B71A3808A13BEE5D4E8392).
  Cambridge occupational reconstructions show long-run movement from
  agriculture toward services in England and Wales, with industrial growth
  varying by place and period; do not hard-code a single inevitable
  farmer-to-factory transition.
  [Cambridge occupational structure study](https://www.repository.cam.ac.uk/items/a021d1cc-5766-4d86-bd14-5ece7e9f8a55).
- Work was often **mixed and seasonal**. A linked-census study of an English
  hosiery village finds that household members' home work remained important
  during factory transition.
  [Rose, 1851/1881 household study](https://journals.sagepub.com/doi/10.1177/036319908801300111).
  U.S. historical labor research finds pronounced agricultural seasonality
  and possible summer agricultural work by manufacturing workers.
  [Engerman and Goldin, seasonality](https://www.nber.org/papers/h0020).
  A seasonal sideline should therefore change *hours and output* without
  repeatedly relabeling a person's occupation.

The game's United States, China and Japan labels are not themselves mobility
parameters. Land access, debt, apprenticeship, markets, transport, policing,
industrial capacity, and household options should create differences. The
historical sources cover specific places and samples; they do not establish
one annual switching rate for all three nations.

## Evaluation of commits `70decf4` through `7f60975`

The combined changes are a substantial improvement on the original churn.
The same 50-turn seed-777, all-AI, three-nation snapshot analyzer was run
before and after the six commits. The newer run was repeated byte-for-byte.
This comparison includes the price and market commit, so it **does not isolate**
the effect of each career rule. The analyzer and outputs live under
`tmp/analyze_careers_50.py` and `tmp/analysis/` and are ignored scratch data.

| Measure | Earlier run | Current run |
|---|---:|---:|
| Observed end-of-turn occupation switches, 50 turns | 8,291 | 1,190 |
| Switches per surviving resident-turn | 9.9% | about 1.1% |
| Immediate `A → B → A` reversals | 2,325 (28.0% of switches) | 119 (10.0%) |
| Turn-50 food career share, U.S. / China / Japan | 28% / 31% / 28% | 85% / 82% / 81% |
| Turn-50 wage employment share, U.S. / China / Japan | 64% / 16% / 11% | 5% / 4% / 6% |
| Deaths, 50 turns | 95, including 52 starvation | 82, including 7 starvation |

The current run has far less hunger, but agriculture absorbs nearly all
population growth. Turn-50 GDP was about 1,820 / 4,289 / 3,967 for the U.S. /
China / Japan, compared with 5,344 / 9,619 / 10,970 in the older run. This is
not a clean GDP effect estimate: market pricing, population, production and
career rules all changed. Living residents rose from 1,192 to 3,740 in
50 agent years; child production and reproduction also confound the
career counts. It is a balance warning that the game may have
traded volatile industrialization for near-universal farming. Mean food
reference prices were pinned at 1.00 in all three countries throughout the
current run; audit whether the new price discovery and available demand give
credible signals for nonfood production. Unrest remained high (8–9 at turn
50), despite food abundance.

What the commits do well:

1. `70decf4` routes ordinary demographic switching around the scheduler and
   adds a common `apply_career_switch` trace path; building staff are less
   likely to be silently reassigned. Hiring with a region now uses the shared
   offer check.
2. `d645582` and `a7cdfae` add lifecycle, tenure and entry friction, which
   help occupations persist across short price changes.
3. `2847d02`, `815854c` and `7f60975` stop hungry farmers from making an
   emergency jump out of food, smooth recent sales, check payroll, reduce herd
   entry, prioritize productive inputs, and block independent craft entry
   without supply. The 50-turn run confirms a large reduction in churn.

What still needs repair:

1. **Clock semantics need to be explicit.** The current `career_lifecycle_age()`
   correctly advances one agent year each turn, but the UI's seasonal year
   advances only every ten turns. The previous follow-up incorrectly treated
   the seasonal label as the agent lifecycle clock. The current 1.1% switch
   rate per resident-turn is already a per-agent-year rate, though its
   denominator includes children and other ineligible residents. Never tune
   the rate by multiplying by ten.
2. **Child roles remain cosmetic.** `region_production.produce()` does not
   check career-entry age, and `demographics_reproduction.handle_reproduction()`
   checks birth spacing but no age. Newly born residents can still produce
   and reproduce while the career chooser calls them children. Their inherited
   career labels inflate food-worker counts.
3. **One field carries several concepts.** `Agent.output` represents a
   producer's trade, a firm's product, a trader's category, a soldier's role,
   and an infant's inherited label. `apply_career_switch` also resets
   `last_career_switch` even when the new output is unchanged; same-trade
   hiring can erase tenure without counting an occupation change.
4. **Alternatives are narrow.** `independent_return` permits only food, wood,
   and furniture. `skill_tier_for_good` places every other good in a closed
   independent tier. The new multi-good market can clear wool, cotton and
   cloth, but household entry into those livelihoods is blocked even where
   land, tools, a buyer and material are available. This contributes to the
   food concentration and limits the intended cotton transition.
5. **Rules are spread across employment routes.** Regular turns use the
   scheduler, but `demographics_career` retains a fallback when it is absent.
   Building assignments, migration, military service and trader conversion
   also change output. Each route needs a clear job/occupation distinction
   and one set of invariants; otherwise a label change can masquerade as a
   lifelong career change.
6. **Some emergency locks are too blunt.** A hungry person labeled a food
   producer is held in that occupation unless marked dispossessed, even if
   their actual plot/access cannot produce enough food. The mobility cohort
   also excludes residents with cash above 150, regardless of their land or
   employment situation. Evaluate feasible food production and actual
   livelihood loss instead of treating the label or cash threshold as proof
   that they need no alternatives.

## Implementation phases

### Phase 0 — Name both clocks and establish a reliable baseline

**Files:** `labor_choice.py`, `agent.py`, `demographics_reproduction.py`,
`region_production.py`, `sim_server/sim_server.py`, analysis runner and tests.

1. Add explicit `agent_age_years()` and `seasonal_cycle_phase()` helpers (or
   equally clear names) and test both clocks. Keep the existing career age
   increment of **one per turn** and the existing ten-phase crop season. Do
   not introduce a generic `TURNS_PER_YEAR` constant or divide age by ten.
   Preserve contract and demographic durations in agent turns.
2. Distinguish founding adults, native-born children, and scenario-created
   adults with explicit age/year metadata. Remove the `birth_round` and
   `last_career_switch` heuristic that infers whether an agent is a child.
3. Audit child production, food consumption, reproduction, taxes, military
   enlistment, hiring and mortality together. Define dependent activity and
   consumption explicitly. Scenario-specific child labor, if allowed, uses
   hours, age, policy and harm; it does not grant a full adult career at birth.
4. Capture an adult-worker baseline by nation and turn. Count permanent
   occupation changes, employer changes, temporary work spells, entries,
   exits, births, deaths and migration separately. Use employed/eligible adult
   person-years for external comparisons, and all-adult person-years for the
   game's broad livelihood transition rate. Store the code version and seed.

**Gate:** A 50-turn game advances fifty agent years and five seasonal cycles;
every age gate agrees with the agent clock. The same runner repeats exactly.
Every stock change
reconciles with births, deaths, migration and categorized transitions.

### Phase 1 — Separate occupation, job, and seasonal activity

**Files:** `agent.py`, `labor_choice.py`, `economy/labor_mobility.py`,
`demographics_career.py`, `region_logistics.py`, `buildings.py`, `army.py`.

1. Preserve `output` as the actual production sector initially, but add a
   stable `primary_livelihood`, `employment_status`, and dated livelihood
   episode. Employer changes in the same sector update job status without
   resetting occupation tenure. Military service and trading are statuses or
   spells unless a person genuinely abandons their prior trade.
2. Route all permanent occupation changes through one operation. Require a
   named reason and reachable destination; update skills/tenure and trace
   exactly once. Reject same-output calls as no-ops. Route hiring, firing,
   migration and temporary work through their own traced operations. A forced
   assignment, debt-bound contract or workhouse placement must be identified
   as such and must not be counted as a freely chosen career.
3. Represent off-season foraging, woodcutting, hauling and household craft as
   limited work-time allocations where existing production supports them.
   A sideline cannot yield a full second occupation's output or double-count
   hours. Keep tenancy/sharecropping distinct from payroll employment.

**Gate:** Employment rosters and contracts reconcile; occupation and job
changes have separate counts; seasonal activities do not produce false
occupation transitions or extra food/cash.

### Phase 2 — Replace rigid switching with feasible, shock-aware choice

**Files:** `economy/labor_mobility.py`, `labor_choice.py`, `livelihood_access.py`,
`region_market.py`, `government.py`.

1. For each candidate, forecast a small number of turns of attainable food,
   take-home cash, input/transport cost, tools and credit, usable land,
   employment security, contract restrictions and household food need.
   Include only executable offers, plots, apprenticeships and markets. Do not
   use current price times hypothetical output as income.
2. Compare staying, a sideline, local employer change, migration, tenancy,
   apprenticeship and a true occupation change. Hunger may raise urgency but
   cannot automatically make farming feasible without land or permit a
   distant job without a vacancy. A temporarily poor harvest should favor a
   sideline, stored food or relief when available over instant retraining.
3. Add specific transition triggers: entry into adulthood, marriage or a
   household split, loss or restoration of land, eviction, firm closure,
   technology displacement, sustained wage gain, severe debt, war service,
   and migration. Normal switches require a persistent expected advantage;
   forced displacement waives waiting but still needs a feasible destination.
4. Replace the universal tier table with activity-specific prerequisites.
   Cultivation needs land/access; independent furniture needs wood, tools and
   buyers; cotton/wool can be grown or gathered where terrain and tenure
   permit; cloth can be household piecework, apprenticeship or factory wage
   labor with distinct productivity. A firm may supply tools but must fund
   payroll and inputs. Permit return to a prior trade with retained skill,
   but charge actual re-entry costs and avoid a mechanical forever ban.
5. Let market crowding, inventory and unmet demand affect prospective
   entrants. Limit implausible simultaneous entry by finite tools, plots,
   vacancies and buyers, not by an arbitrary percentage of all residents.

**Gate:** A poor worker with commons may stay independent; a dispossessed
worker can take a funded job or tenancy; a firm closure creates unemployment
or migration when no destination exists. Food producers do not abandon a
shortage region for a one-turn price spike. At least two economic paths work
under matched seeds: protected subsistence and profitable wage expansion.

### Phase 3 — Calibrate flows and make them legible

**Files:** `run_trace.py`, `metric_catalog.py`, `trace_snapshots.py`,
`sim_server/sim_server.py`, `web_client/client.js`, desktop UI, benchmark tests.

1. Publish per nation and region: adult occupation matrix, job-status matrix,
   food-producing adult hours, sideline hours, youth entry, permanent switch
   reasons, forced vs voluntary changes, wage after food/debt deductions,
   and migration. Provide individual histories on inspection.
2. Use historical evidence as *order-of-magnitude and shape* checks, not a
   mandatory global quota. For initial tuning, measure ordinary broad
   occupation changes over **one agent turn/year** and compare with a declared
   game target of roughly 3–8% of eligible adults per agent year, with higher
   youth and shock rates. This range is a starting design target, not an
   estimate for nineteenth-century China, Japan, or the United States.
   Expect many employer and seasonal-work changes without primary-occupation
   change. Reversal and sector-concentration targets must be tuned against
   actual production and livelihoods, not only switch count.
3. Run multiple paired seeds under land protection, enclosure, cash tax,
   wages, mechanization, harvest failure and relief. Report adult switch
   rates, reversals within an agent year or over short multi-turn spans,
   food/calorie security, occupation shares,
   input availability, real wages, profits, output, GDP, unrest and deaths.
   Include a replay test for every occupation mutation source. Recheck the
   price trace: a price pinned at 1.00 despite a shock needs an explanation
   from bids, asks, inventories and policy.
4. In the UI, show why a cohort moved: e.g. “land access lost; 18 cultivators
   took funded mill jobs, 7 entered tenancy, 11 remained without work.” Show
   the costs to food supply, coercion and enforcement, employer profits,
   unrest, and rival capacity next to the decision. Avoid
   treating a change in product label as a social transformation.

**Gate:** The trend has at least two viable player strategies with visible
costs; crisis transitions are responsive but temporary price noise does not
erase careers. An ordinary country no longer converges mechanically to
80%+ food careers, and stopping mass churn does not recreate starvation or
freeze industrial development.

## First implementation slice

Start with **Phase 0 and the narrow mutation invariant from Phase 1**:
explicit dual-clock helpers; preserve one-year-per-turn career age; explicit
native-child flag; no full adult production/reproduction by infants; same-output calls do
not reset tenure; and a benchmark that separates adult occupation changes
from employment changes. This makes every later rate and age comparison
interpretable before tuning hurdles, prices or additional career paths.

### First-slice status (2026-10-17)

The two-clock rule is recorded in the main `gdd.md` and
`game_time_design.md`. The first code pass adds explicit native-child status,
age-scaled dependent food need, conserved parent-to-child food sharing,
under-14 production/foraging/hiring exclusions, dependent-aware food security
forecasts, an under-18 reproduction gate,
and a no-op for same-trade career mutations. `benchmark_career_mobility.py`
counts adult occupation and employer changes separately over 50 agent years.

In the seed-777 default three-nation run, adult occupation changes were
1.52% (United States), 1.21% (China), and 1.50% (Japan) per adult agent-year;
adult food-career shares still ended at 77.7%, 90.4%, and 86.0%. Reported
starvation deaths were 9, 0, and 0. The child gate did not make nonfarm
livelihoods viable, and the United States result needs food-balance review.
The benchmark's `exits` counts
people missing from the next snapshot; they must **not** be interpreted as
reported deaths. Before calibrating flows, categorize every exit route and
reconcile person stocks with births, deaths, migration, and role conversion.
Then continue with Phase 1's occupation/job distinction and Phase 2's
feasible livelihood choices. These are the remaining gates, not conclusions
established by the first slice.
