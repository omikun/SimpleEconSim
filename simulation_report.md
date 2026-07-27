# Economic Simulation Evaluation Report — 200 Cycles

![Simulation Output Graphs](sim_output.png)

---

## 1. Simulation Parameters

| Parameter | Value |
|---|---|
| Initial agents | 110 (90 Farmers, 7 Woodcutters, 2 Carpenters, 0 Gov) |
| Cycles run | 200 |
| Max food production (doubled at t=100) | 10,000 → 20,000 |
| Max wood production | 3,000 |
| Max furniture production | 300 |
| Starvation limit (steps) | 20 |
| Birth probability | 0.04 |
| Death probability | 0.10 |
| Birth gap | 7 rounds |
| Max career switches | 5 |

---

## 2. Final Population Overview

| Sector | Population | % of Total |
|---|---|---|
| **Farmers (Food)** | 135 | 47.2% |
| **Woodcutters (Wood)** | 80 | 28.0% |
| **Carpenters (Furniture)** | 71 | 24.8% |
| **Government** | 0 | 0.0% |
| **Total** | **286** | **100%** |

Population grew from 110 to 286, a **160% increase** over 200 cycles. No agents starved to death (dead/starved = 0), indicating the economy sustained its population well.

---

## 3. Sector-by-Sector Analysis

### 3.1 Farmers (Food) — Pop: 135

| Metric | Final Value |
|---|---|
| Population | 135 |
| Price per unit | $0.85 |
| Total inventory | 1,457 |
| Total cash held | $2,109.89 |

- **Largest sector** by population and cash reserves.
- Price declined from $1.00 → $0.85 over the simulation, likely due to the production capacity doubling at t=100.
- Food inventory remained abundant (1,457 units), ensuring no starvation events.

### 3.2 Woodcutters (Wood) — Pop: 80

| Metric | Final Value |
|---|---|
| Population | 80 |
| Price per unit | $1.22 |
| Total inventory | 1,201 |
| Total cash held | $778.64 |

- Steady growth driven by carpenter demand for wood inputs.
- Price rose modestly ($1.00 → $1.22), reflecting sustained demand from furniture production.
- Healthy inventory buffer of 1,201 units.

### 3.3 Carpenters (Furniture) — Pop: 71

| Metric | Final Value |
|---|---|
| Population | 71 |
| Price per unit | $2.37 |
| Total inventory | 808 |
| Total cash held | $694.98 |

- **Strongest price appreciation** ($1.00 → $2.37) — furniture commands a premium as a processed good.
- Grew from 2 to 71 agents, a **3,450% increase**, showing high demand for value-added goods.
- Lower per-capita cash than farmers, but strong inventory levels.

### 3.4 Government — Pop: 0

- Government agents did not sustain; the gov profession is a consumer-only role with no production capability.
- Without production output, gov agents could not generate income in the market.

---

## 4. Corporate Sector

| Metric | Value |
|---|---|
| Active corporations | 6 |
| Total employees | 30 |

| Corporation | Employees | Cash | Wage |
|---|---|---|---|
| agent160-F | 15 | $340.04 | $5 |
| agent244-F | 15 | $341.27 | $5 |
| agent210-F | 0 | $0.97 | $32 |
| agent206-F | 0 | $16.15 | $35 |
| agent198-F | 0 | $0.18 | $42 |
| agent197-C | 0 | $0.25 | $44 |

- Two large farming corporations employ 15 workers each at minimal wages ($5), accumulating substantial cash reserves ($340+).
- Four corporations have zero employees and near-zero cash — these are failed ventures where wages outpaced revenue.
- The wage dynamics show a pattern: successful corps drive wages down to the floor ($5), while failed corps had wages too high ($32–$44) to sustain profitability.

### Why Failed Corporations Had Runaway Wages

The wage escalation is caused by an **asymmetric ratchet mechanism** in `RunLaborMarket`:

**Upward pressure (fast):**
- **Rule 6 — Cash > $600** triggers a 5% raise every turn. New corps form with $200–400 cash, and with owner equity + bank loans, they temporarily cross the $600 threshold, compounding wages upward each turn.
- **Rule 4b — Poaching** inflates wages via `max(old_wage × 1.2, agent.wage × 1.1)`. A poaching war between two cash-rich corps can spike wages 10–20% in a single turn.

**Downward pressure (slow):**
- **Rule 6 — Low cash** only decreases wages by 5% per turn (`agent.wage × 0.95`), even when the corp is hemorrhaging cash.

**The death spiral:**
1. New corp briefly has cash > $600 → wage ratchets up via 5% raises and poaching.
2. Once at a high wage (e.g., $40), payroll burns cash faster than revenue — food sells at $0.85, so a $40/worker wage can't be covered.
3. The 5%/turn wage decrease is **too slow** to outrun the burn rate.
4. Layoffs trigger, then dissolution — leaving a shell corp with $0 employees and near-zero cash.

**Successful corps** (agent160, agent244) either never triggered the cash > $600 rule or had wages driven down fast enough through layoff cycles to reach the $5 floor, where 15 employees × $5/turn is sustainable.

---

## 5. Key Observations

1. **Sustainable Growth**: The economy supported a 2.6× population increase with zero starvation deaths. Food production kept pace with population growth.

2. **Supply Chain Health**: Wood production (input) → Furniture (output) chain functioned well. Carpenters grew to become the second-largest profession, validating the multi-stage production model.

3. **Price Dynamics**: Food prices declined (supply glut after t=100 capacity doubling), while wood and furniture prices rose — consistent with supply/demand mechanics.

4. **Corporate Consolidation**: Only 2 of 6 corporations survived with employees. Successful corporations converged to minimum wage ($5) and maximum headcount (15). Failed corporations had wage levels 6-8× higher, suggesting that aggressive wage competition without sufficient cash reserves leads to rapid collapse.

5. **Wealth Distribution**: The Gini coefficient graphs (visible in the output) track inequality within each profession. Farmers hold the most aggregate cash ($2,109) but also have the largest population.

6. **No Government Sector**: The gov profession went extinct — without production capability, these agents cannot participate meaningfully in a production-and-trade economy.

---

## 6. Graphs Included

The composite graph (`sim_output.png`) displays 16 panels:

| Panel | Description |
|---|---|
| Population vs Time | Log-scale population by profession + total + deaths |
| Inventory vs Time | Aggregate inventory levels per good |
| Gini Coefficient | Wealth inequality per profession over time |
| Demand Ratio vs Time | Log-scale demand ratios |
| Production vs Time | Units produced per round (log scale) |
| Inventory Per Capita | Non-producer inventory per good |
| Cash vs Time | Cash by profession + total + bank |
| Demand vs Time | Log-scale absolute demand |
| Sold vs Time | Units sold per round (log scale) |
| Price vs Time | Price evolution (log scale) |
| Hunger vs Time | Number of hungry agents (log scale) |
| Supply vs Time | Units supplied per round (log scale) |
| Farmer/Woodcutter/Carpenter/Gov Purchases | Per-profession buying patterns |

---

*Report generated from econsim.py — 200-cycle run on 2026-06-28.*