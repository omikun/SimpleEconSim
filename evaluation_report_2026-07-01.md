# Economic Simulation Evaluation Report
**Date:** 2026-07-01
**Cycles:** 400
**Population Cap:** Removed (was 512)

---

## Executive Summary

The economy sustained 707 agents after 400 cycles, with 4 active corporations employing 55 workers. Population grew continuously without the 512 cap, reaching 707 with no signs of collapse. The bank earned $25,119 in loan interest and paid $19,243 in deposit interest, yielding a 1.31x profit ratio.

---

## Population & Demographics

| Group | Population | Cash |
|---|---|---|
| Farmers (F) | 311 | $3,177 |
| Loggers (W) | 102 | $449 |
| Carpenters/wood (C) | 294 | $1,636 |
| Government (G) | 0 | $0 |
| **Total** | **707** | **$5,262** |
| Dead/Starved (cumulative) | 16 | |

- **Growth:** From 110 → 707 over 400 cycles (~1.5x per 100 turns)
- **Death toll:** Only 16 cumulative deaths (old age + starvation)
- **Most populous sector:** Farmers (44%) — consistent with food being the basic necessity
- **Sector imbalance:** Loggers underpopulated (14%) vs. Carpenters (42%), despite Carpenters needing wood inputs

---

## Labor Market

| Corporation | Sector | Employees | Capacity | Wage | Cash |
|---|---|---|---|---|---|
| agent551-F | Food | 12/12 | $1 | $60.96 |
| agent556-F | Food | 24/24 | $1 | $438.04 |
| agent564-W | Wood | 16/16 | $1 | $63.05 |
| agent565-C | Carp | 3/12 | $1 | $5.31 |

- **4 active corporations** employing 55 agents (7.8% of population)
- **All wages at $1** (the floor) — no wage competition happening
- The food sector dominates corporate activity (2 of 4 corps, 36 of 55 employees)
- agent565-C (carpenter) is struggling — only 3/12 employees and $5.31 cash
- Wages are stuck at the floor due to low food prices ($0.43) keeping `max(1, food_price/3)` = 1

---

## Prices & Production

| Good | Price | Inventory |
|---|---|---|
| Food | $0.43 | 4,934 |
| Wood | $0.25 | 4,205 |
| Furniture | $0.49 | 3,757 |

- **Deflation across all goods** — prices dropped from starting $1 to $0.25-$0.49
- Massive inventory buildup (4,934 food for 311 farmers = 15.9 food/farmer)
- Production far outpaces consumption, creating deflationary pressure
- Furniture priced at $0.49 is likely below cost to produce (requires 2 wood inputs at $0.25 each + labor)

---

## Money & Banking

| Metric | Amount |
|---|---|
| Cash in economy (total) | $22,349.83 |
| Agent cash | $5,262.10 |
| Bank equity (deposits - liabilities) | $17,087.73 |
| Bank deposits held | $175,506.32 |
| Bank loans outstanding | $158,418.59 |
| **Loan interest earned** | **$25,119.24** |
| **Deposit interest paid** | **$19,242.69** |
| **Net bank profit** | **$5,876.55** |
| **Profit ratio (earned/paid)** | **1.31x** |

- **76.5% of total cash** sits in bank equity ($17,088 of $22,350)
- Bank deposits ($175.5k) vs. agent cash ($5.3k) = **33:1 ratio** of deposited to circulating cash
- The bank earned 31% more in loan interest than it paid in deposit interest
- Despite Fixes 1 & 4 (withdraw-before-borrow), agents still deposit more than they withdraw

---

## Key Observations

1. **No population cap effect:** Without the 512 limit, population grew to 707 with sustained growth. However, inventory accumulates faster than population, suggesting overproduction.

2. **Wage stagnation:** All corps pay $1. The wage floor formula `max(1, food_price/3)` keeps wages at 1 when food prices are below $3. With food at $0.43, wages have no upward pressure.

3. **Deflationary spiral:** Low prices → low wages → low income → low spending → low prices. The economy is productive but agents can't capture the value.

4. **Corporate fragility:** agent565-C near bankruptcy ($5.31 cash). If it dissolves, 3 employees return to independent work, reducing corporate employment share.

5. **Bank is profitable but not predatory:** 1.31x profit ratio means for every $1 paid to depositors, the bank earns $1.31 — reasonable spread.