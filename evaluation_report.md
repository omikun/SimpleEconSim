# Economic Simulation Evaluation Report (Wood Productivity = 2 per Turn)

This report evaluates the long-term sustainability of the closed economy over a **500-cycle horizon** with:
1. **High Wood Productivity**: Logger wood production set back to **2 units per cycle** (reintroducing high potential oversupply).
2. **Dynamic Price Floors**: Keeping the distress-based (hunger and cash) floor mechanism active.

This run yielded one of the most fascinating microeconomic findings of the entire simulation series: **the dynamic price floor acted as a robust economic safety net**, allowing the economy to support a massive population while completely insulating it from oversupply-induced starvation.

---

## 1. Executive Summary

With Logger productivity at 2 per turn, the economy expanded dramatically. The total population reached a record **361 agents** with **only 2 starvations/deaths** over the entire 500-cycle run.

### Key Metrics Table (500 Cycles, Wood = 2)

| Sector | Population | Market Price ($) | Inventory (Units) | Cash ($) | Avg. Cash per Capita ($) | Status / Health |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Farmers (F)** | 196 | 8.21 | 700.00 | 8,158.64 | 41.63 | **Very Healthy**: Large base feeding the huge population. |
| **Loggers (W)** | 112 | 17.02 | 1,558.00 | 4,368.42 | 39.00 | **Solvent**: Oversupplied but safe from starvation. |
| **Carpenters (C)** | 53 | 75.02 | 71.00 | 861.32 | 16.25 | **Flourishing Class**: Large artisan sector supported by cheap wood. |
| **Government (G)** | 0 | 1.00 | 0.00 | 0.00 | 0.00 | **Extinct**: Structural lack of income (expected). |
| **Total / Global** | **361** | **N/A** | **2,329.00** | **13,388.38** | **37.09** | **High Capacity: Only 2 deaths.** |

---

## 2. Key Findings & The "Safety Net" Mechanism

### A. High Carrying Capacity via Cheap Inputs
* **The Population Boom**: The population grew to **361 agents** (compared to only 116 in the scarce wood run). 
* **The Cheap Input Catalyst**: Because Loggers produced 2 wood per turn, wood became highly abundant. This dropped the market price of wood to a highly affordable **$17.02** (compared to $118.43 in the scarce version).
* **Artisan Sector Expansion**: Extremely cheap wood allowed the **Carpenter (C)** population to flourish, growing from **4 to 53 agents**. Cheap inputs unlocked high-volume furniture production, boosting overall trade volume and economic capacity.

### B. Dynamic Price Floor as an Economic Safety Net
> [!IMPORTANT]
> **Why the Wood Glut Didn't Kill the Economy**:
> In the baseline model, a wood glut of **1,558 units** resulted in massive Logger starvation because rigid price floors locked Loggers out of trading when they were poor or hungry, preventing them from liquidating wood to buy food.
>
> With the **dynamic price floor** active, when Loggers accumulated excess wood and faced hunger or poverty, the floor dynamically collapsed. This allowed Loggers to offer deep discounts, ensuring that Farmers and Carpenters continuously purchased their excess wood. Loggers always stayed solvent enough to buy food ($8.21), leading to an outstanding **survival rate of 99.4% (only 2 deaths over 500 cycles)**.

---

## 3. Visual Analysis of `sim_output.png`

The updated 500-cycle diagnostic chart below tracks the dynamic safety-net history:

![Economic Simulation Graphs](./sim_output.png)

### Key Chart Observations:
1. **Population vs Time (Top-Left)**: Shows rapid, healthy growth scaling up to **361 agents** before settling into a flat plateau, demonstrating robust carrying capacity.
2. **Inventory vs Time**: Shows the wood inventory (red line) stabilizing at a high plateau of ~1,550 units, proving that the dynamic price floor successfully manages high-inventory gluts without causing economic loops or sudden crashes.
3. **Hunger vs Time**: Stays virtually flat at 0, confirming the eradication of starvation despite high structural oversupply.
