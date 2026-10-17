# Career Switching Realism & Lifecycle Mobility Implementation Plan

Date: 2026-10-16

**Follow-up audit:** Phases 1–4 and two related market commits have been
implemented. [The follow-up plan](career_mobility_followup_plan.md) evaluates
their combined outcome and supersedes this document's numerical calibration
targets. The [game time design](game_time_design.md) explicitly keeps **one
agent year per turn** alongside **ten turns per seasonal cycle**. Historical
annual mobility evidence can inform one-turn agent choices when the occupation
definition and eligible population match.

## 1. Empirical Audit of Recent Simulation Traces

### 1.1 Career Switching Frequencies in Recent Traces

| Trace File | Seed / Scenario | Horizon | Total Career Switches | Survivor Person-Turns | Switch Rate (per person-turn) | Employment Status Changes |
|---|---|---:|---:|---:|---:|---:|
| `tmp/analysis/default_three_nation_50_careers_run2.json` | `777` (3-nation Voronoi) | 50 turns | **8,291** | 84,037 | **9.87% / turn** | 1,797 (2.14% / turn) |
| `tmp/analysis/default_three_nation_50_careers.json` (`run1`) | `777` (3-nation Voronoi) | 50 turns | **7,690** | 85,058 | **9.04% / turn** | 817 (0.96% / turn) |
| `tmp/traces/baab7eff42384930a8552e4e42a666ac-1.ctr` | `777` (3-nation Voronoi) | 10 turns | **1,025** (`independent_career_decision`) | ~11,967 | **8.57% / turn** (1,046 net end-of-turn) | 4 hires + 11 subsistence exits |
| `tmp/traces/4957116f6a284218b9f0f3d4842ed360-1.ctr` | `90210` (default) | 30 turns | **2,107** (`independent_career_decision`) | ~44,500 | **~4.73% / turn** (independent only) | 319 hires + 239 subsistence exits |

### 1.2 Breakdown of `default_three_nation_50_careers_run2.json` (50 Turns)

1. **By Nation**:
   - **United States**: 2,251 switches across 18,245 person-turns (**12.34% / turn**), 909 employment changes.
   - **China**: 2,798 switches across 29,658 person-turns (**9.43% / turn**), 497 employment changes.
   - **Japan**: 3,242 switches across 36,134 person-turns (**8.97% / turn**), 391 employment changes.
2. **Repeat Switching & Lifetime Churn**:
   - **2,486 unique agents** switched careers at least once out of ~2,585 total ever-living agents (**~96% of the population**).
   - Mean switches per switcher: **3.34 switches** within a 50-turn window (an implied **~5.0 switches per 50 turns** across all person-turns).
   - Distribution of switch counts per switcher:
     - 1 switch: 390 agents
     - 2 switches: 534 agents
     - 3 switches: 551 agents
     - 4 switches: 448 agents
     - 5 switches: 268 agents
     - 6–13 switches: 295 agents (up to 13 switches in 50 turns).
3. **Ping-Pong Reversals (`A -> B -> A`)**:
   - **2,325 immediate reversals** out of 8,291 total switches (**28.0% of all switches** simply undo the agent's previous switch).
   - Dominant transition pairs:
     - `food -> wood` (1,552) and `wood -> food` (1,176)
     - `furniture -> food` (800) and `food -> furniture` (751)
     - `wood -> furniture` (599) and `furniture -> wood` (455)
     - `food -> porcelain` (389) and `porcelain -> food` (276)
     - `transport -> food` (275) and `food -> transport` (248)
     - `wool -> food` (255) and `wool -> wood` (186)
4. **Inter-Switch Turn Intervals**:
   - Consecutive switches for the same person occur with turn gaps of:
     - **Gap = 1 turn**: 583 switches (back-to-back turns)
     - **Gap = 2 turns**: 384 switches
     - **Gap = 3 turns**: 259 switches
     - **Gap = 4 turns**: 801 switches (exact expiration of the 4-turn cooldown in `LaborMobilityScheduler`)
     - **Gap = 11 turns**: 367 switches (exact expiration of the `> 10` turn cooldown in `demographics_career.py`)

---

## 2. Root-Cause Diagnosis in Current Code

### Cause 1: Two Competing, Uncoordinated Switching Engines Fighting Each Other
Every turn in `micro/region/stepper.py:step_economy`, an independent agent is evaluated by **two separate career-switching systems** with contradictory rules:
1. **`economy/labor_mobility.py:LaborMobilityScheduler.step_labor_cohort` (Line 108, pre-production)**:
   - Evaluates `independent_return(region, worker, g, producer_count)`, which explicitly returns `0.0` (`'no independent local market'`) for every good except `Goods.food`, `Goods.wood`, and `Goods.furniture` (lines 47–48).
   - Switches workers into whichever of `{food, wood, furniture}` had the highest 3-turn trailing `sold_log` revenue + subsistence value.
2. **`demographics_career.py:handle_career_switching` (called via `live(region, t)` at Line 229, post-market)**:
   - Switches hungry non-farmers to `Goods.food` (`rand.random() < 0.55 * hunger_pressure`, lines 125–131) **without checking `last_career_switch`**—which can overwrite a switch made by `LaborMobilityScheduler` earlier in the *exact same turn*.
   - Switches poor (`cash < 20`) or hungry farmers into `ctx.most_demand` or `learned_switch_choice` across **all goods** (`porcelain`, `wool`, `cloth`, `transport`, `nitrates`, etc., lines 132–179).
   - On the very next turn (or 4 turns later), `LaborMobilityScheduler` sees `current_return == 0.0` for `porcelain`/`wool`/`cloth`/`transport` and immediately forces those agents back into `food`, `wood`, or `furniture`.
   - Furthermore, mutations in `demographics_career.py`, `buildings.py:Building.step` (line 338), and `region_logistics.py` do not emit `labor.career_choice` trace events.

### Cause 2: Emergency Fast-Path Cooldown Bypass & Counter-Productive Food Exit
In `economy/labor_mobility.py` (lines 126–134 and 224):
- Any unemployed worker with `hungry_steps > 0` is flagged `is_emergency = True`, bypassing both the cohort schedule (`_n_groups`) and the 4-turn cooldown (`is_emergency or (t - last_career_switch >= 4)`).
- Worse, a hungry farmer (`worker.output == Goods.food`, `hungry_steps == 1`) in `is_emergency` mode can be switched **out of `Goods.food` into `Goods.furniture` or `Goods.wood`** (as observed in `baab7eff42384930a8552e4e42a666ac-1.ctr` Turn 2, event `#154095`, where 179 agents mass-switched into `furniture`), causing acute food shortages 1–2 turns later and triggering a mass `furniture -> food` stampede on Turn 4 (428 switches).

### Cause 3: Herd Cobweb Oscillations in `independent_return`
In `economy/labor_mobility.py:independent_return` (lines 57–64):
- `sales_per_producer` divides trailing `sold_log` by `producer_count`, but `expected_sales = min(saleable, sales_per_producer) * price` remains flat at `saleable * price` as long as `sales_per_producer >= saleable`.
- When `furniture` or `wood` clears well on Turn $t-1$, dozens of agents in the cohort see the exact same un-dampened return and simultaneously pile into that sector in a single turn, overshooting demand and collapsing per-producer sales on Turn $t+1$.

### Cause 4: Zero Lifecycle / Age Structure or Occupation-Specific Human Capital
- **No age effect on switching**: Neither `LaborMobilityScheduler` nor `demographics_career.py` nor `labor_choice.py` checks `agent.age(t)`. A 70-turn-old master artisan switches careers just as easily as an 18-turn-old entrant.
- **Compressed founder age distribution & newborn labor**:
  - In `micro/region/core.py:_create_agents` (lines 356, 396, 418), all founding agents are initialized with `birth_round = t` (`0`), making the entire founding population age 0 at start.
  - In `demographics_reproduction.py:handle_reproduction` (line 82), newborn agents (`birth_round = t`, `age = 0`) immediately enter the labor and career-switching pool on the next turn without a childhood/apprenticeship maturation phase.
- **No occupation-specific tenure or switching costs**: Agents have no accumulated skill/tenure in their current craft and pay zero capital/retooling cost when switching from farmer to carpenter or potter.

---

## 3. Historical & Empirical Benchmarks on Career Switching

### 3.1 Age Profile of Career Mobility (Lifecycle Human Capital & Jovanovic Job-Shopping)
Across both modern longitudinal datasets (NLSY79, PSID) and historical linked census records:
- **Gueorgui Kambourov & Iourii Manovskii (2008, 2009 — *Review of Economic Studies* / *International Economic Review*)**:
  - Occupation-specific human capital (returns to occupational tenure of ~12–20% over 5 years) creates an endogenous rising opportunity cost of switching occupations as workers age.
  - True 1-digit / broad-sector occupational mobility in the PSID falls sharply with age:
    - **Youth / Early Career (Ages 18–25)**: High exploratory "job shopping" (Jovanovic 1979; Topel & Ward 1992), with broad occupational switch rates of **~8–12% per year** (and ~50–60% of lifetime career switches occurring before age 30).
    - **Prime Working Age (Ages 26–45)**: Rapid stabilization as craft/occupational tenure accumulates; broad-sector switch rates fall to **~3–5% per year**.
    - **Mature / Late Career (Ages 45+)**: Strong occupational lock-in; broad-sector switches drop to **< 1–2% per year**, occurring almost exclusively under involuntary displacement (firm closure, enclosure, famine, technological obsolescence).

### 3.2 Historical Era & Structural Transformation Trends (19th vs. 20th Century)
1. **Structural Directionality vs. Symmetric Ping-Ponging (Kuznets / Polanyi / Beckert)**:
   - Historically, 19th-century occupational transitions were **structurally directional**, not symmetric back-and-forth oscillations:
     - **Enclosure & Proletarianization**: Customary peasants/serfs dispossessed from commons moved one-way into proto-industrial putting-out, navvy construction, or factory wage labor (`food -> cloth/iron/coal/transport`).
     - **Proto-Industrial Bye-Employment (Seasonal / Dual Livelihood)**: Smallholders combined subsistence farming with off-peak timber/textile work rather than abandoning their farm plot every 4 turns.
2. **Cross-National Institutional Differences (Long & Ferrie 2005, 2013 — *AER*)**:
   - **Frontier / Land-Abundant Regimes (19th-Century US)**: Higher geographic and occupational fluidity, including viable mid-life movement into independent homestead/cash-crop farming and artisan trades.
   - **Stratified / Guild & Parish-Bound Regimes (Britain / Europe / Tokugawa-Meiji Japan / Qing China)**: Stronger craft barriers, apprenticeship requirements, settlement laws (Parish Workhouse / Statute of Laborers), and hereditary craft transmission (sons inheriting father's trade).
3. **Industrialization & Deskilling (Habakkuk / Goldin & Katz / Braverman)**:
   - **Artisan Craft Barriers**: Independent skilled trades (`furniture`, `porcelain`, `fine_textiles`, `iron`) required years of apprenticeship, tools, and working capital—barring instantaneous entry by destitute laborers.
   - **Factory Mechanization (`machinery_level`)**: Factory machinery deskilled production, allowing corporate employers (`is_corporation`) to hire unskilled/dispossessed workers across sector boundaries without requiring prior artisan mastery, while simultaneously displacing independent handloom weavers and craftsmen.

---

## 4. Implementation Plan to Make Career Switching Realistic

### Phase 1: Unify Career Mobility into a Single Traced Pipeline
**Files**: `economy/labor_mobility.py`, `demographics_career.py`, `micro/region/stepper.py`, `metric_catalog.py`

1. **Consolidate Decision Authority**:
   - Make `LaborMobilityScheduler` the **single authoritative engine** for regular and emergency occupational transitions during `step_economy`.
   - In `demographics_career.py:handle_career_switching`:
     - Remove the duplicate random post-market career switches (`handle_career_switching` in `Live()`) OR restrict `demographics_career.py` strictly to **apprenticeship subsidy grants** and **job-seeking into existing employers within the same profession**, routing all actual `agent.output` changes through a shared helper `apply_career_switch(region, agent, new_output, turn, reason, ...)` that always updates `last_career_switch` and emits a `labor.career_choice` causal trace event.
2. **Trace Every Occupation Mutation**:
   - Route `attach_worker` (`labor_choice.py`), `make_trader_internal` / `exit_trader` (`region_logistics.py`), and `Building.step` (`buildings.py`) through the same trace emitter so `labor.career_choice` accounts for 100% of career flows.

### Phase 2: Age Distribution, Youth Entry, and Lifecycle Mobility Decay
**Files**: `agent.py`, `micro/region/core.py`, `demographics_reproduction.py`, `economy/labor_mobility.py`

1. **Realistic Initial Age Pyramid**:
   - In `micro/region/core.py:_create_agents`, seed founding adult agents with a realistic age distribution (`birth_round = t - rand.randint(16, 58)`) rather than `birth_round = 0`, preserving deterministic seeding.
2. **Lifecycle Age Hazard Curve $\phi(\text{age})$**:
   - Define an age-dependent mobility multiplier $\phi(\text{age})$ calibrated to Kambourov & Manovskii / Topel & Ward lifecycle curves (where 1 turn $\approx$ 1 year of lifecycle age):
     $$\phi(\text{age}) = \begin{cases} 1.35 & \text{if } 16 \le \text{age} \le 25 \text{ (youth job-shopping phase)} \\ \exp\left(-0.045 \cdot (\text{age} - 25)\right) & \text{if } 25 < \text{age} \le 55 \text{ (prime-age stabilization)} \\ 0.15 & \text{if } \text{age} > 55 \text{ (senior lock-in; switches only under acute crisis)} \end{cases}$$
   - For newborns (`birth_round > 0` with `age(t) < 14`), lock their independent profession to their household/parent trade (`parent.output`) until apprenticeship/entry age (`age == 14..18`), at which point they receive a one-time low-friction **Youth Career Entry** evaluation.
3. **Required Switching Premium Scales with Age**:
   - Instead of a flat `1.25x` return threshold for all ages (`best_return > max(1.5, current_return * 1.25)`), require the hurdle rate to rise with age and lower `ambition` / `risk_tolerance`:
     $$\text{hurdle\_mult}(\text{age}, \text{tenure}) = 1.15 + \frac{0.25}{\phi(\text{age})} + 0.04 \cdot \min(10, \text{tenure})$$

### Phase 3: Occupation-Specific Human Capital (Tenure) & Skill Tier Friction
**Files**: `agent.py`, `region_production.py`, `economy/labor_mobility.py`, `labor_choice.py`

1. **Track Occupational Tenure**:
   - Derive `career_tenure = t - agent.last_career_switch` (or track `agent.career_tenure` / prior experience in `agent.memory['career_xp']`).
   - Apply a modest **learning-by-doing productivity or quality bonus** in `region_production.py` (e.g., $+2\%$ per turn of tenure up to $+20\%$, or preserving partial XP if returning to a previously practiced craft stored in `memory`), giving experienced artisans a realistic reason to stay in their trade through temporary 1-turn market dips.
2. **Skill Tiers & Capital Entry Costs**:
   - Classify goods into skill/capital tiers:
     - **Tier 0 (Subsistence / Unskilled)**: `food`, `wood`, `wool`, `cotton` — low entry barrier; accessible in emergencies.
     - **Tier 1 (Semi-Skilled / Hauling & Extraction)**: `transport`, `coal`, `iron_ore`, `nitrates` — requires basic working capital or firm employment.
     - **Tier 2 (Skilled Artisan Crafts)**: `furniture`, `cloth`, `iron`, `porcelain`, `fine_textiles`, `rum` — independent entry requires working capital (`agent.cash >= input_cost * 2 + tool_cost`), apprenticeship subsidy, or parent inheritance; **corporate firms** (`is_corporation`) bypass the individual tool barrier because the firm owns the machinery (`machinery_level`).

### Phase 4: Fix Emergency Fast-Path, Hysteresis & Herd Cobweb Damping
**Files**: `economy/labor_mobility.py`, `buildings.py`

1. **Prevent Hungry Farmers from Abandoning Food for Artisan Goods**:
   - In `LaborMobilityScheduler.step_labor_cohort`, when `is_emergency` is True (`hungry_steps > 0`):
     - An emergency switch may only move a worker **into a funded wage job** (`HIRED_BY_FIRM` where `offered_wage >= food_price`) or **into `Goods.food`** (if they have land/commons access)—**never** from `Goods.food` into `Goods.furniture` or `Goods.wood`.
     - Enforce a minimum emergency cooldown of `t - worker.last_career_switch >= 2` so an agent cannot switch on consecutive turns ($t$ and $t+1$).
2. **Smooth Expected Return & Marginal Congestion Pricing**:
   - Compute `independent_return` using an exponentially smoothed moving average of clearing sales/prices over 5–8 turns rather than raw 3-turn spikes.
   - Include the **prospective entrant (+1)** in the denominator (`max(1, producer_count + 1)`) and cap per-turn net switches into any single independent sector on a tile to a fraction of unfilled demand (e.g., `max(1, int(0.25 * unmet_demand_units / recipe['production']))`) so 179 agents cannot pile into `furniture` on the same turn.
3. **Fix Building Staffing Poaching (`buildings.py` Line 335)**:
   - Stop `Building.step` from silently overwriting `c.output = good` every turn on random farmers without setting `last_career_switch` or checking cooldowns.

---

## 5. Target Calibration & Verification Gates

| Metric | Current Baseline (`run2`) | Target Post-Fix Range | Historical / Theoretical Basis |
|---|---|---|---|
| **Overall Switch Rate** | **9.87% / person-turn** | **1.5% – 3.5% / person-turn** | Kambourov & Manovskii (2008) 1-digit sector mobility (~2–4%/yr) |
| **Ping-Pong Reversal Share (`A->B->A`)** | **28.0%** of all switches | **< 5%** of all switches | Hysteresis, tenure returns, and marginal congestion damping |
| **Same-Turn / Next-Turn Switches (Gap $\le 1$)** | **583** in 50 turns | **0** (except military mobilization) | Unified pipeline + minimum transition cooldown |
| **Youth vs. Senior Switch Ratio** | **~1.0x** (age-invariant) | **3.0x – 5.0x** (Age 16–25 vs. Age 45+) | Topel & Ward (1992); Long & Ferrie (2013) lifecycle profile |
| **Causal Trace Coverage (`labor.career_choice`)** | Partial (`demographics_career` untraced) | **100%** of career transitions | Phase 4 causal trace completeness gate |
