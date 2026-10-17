# Market Price & Supply-Chain Stabilization Plan

## 1. Executive Summary & Trace Diagnosis

In the 50-turn post-career-fix simulation trace (`default_three_nation`, `seed=777`), career switching stabilized at **1.60% / person-turn** and successfully reallocated labor toward high-priced sectors (`wood` workers expanded from `134` on Turn 15 to `1,074` on Turn 50; `furniture` workers recovered from `68` to `180`). However, four structural mechanics in [`region_market.py`](file:///Users/sli/Code/region_market.py) prevented prices and downstream production from reaching a balanced equilibrium:

1. **One-Way Scarcity Inflation Drift in [`update_price_ref`](file:///Users/sli/Code/region_market.py#L296-L364)**:
   - `scarcity = max(0.0, min(1.0, 1.0 - avg_inv / max(0.1, maxinv * 0.6)))` is strictly non-negative (`[0.0, 1.0]`) and added unconditionally (`+0.30 * scarcity`) to `inflation = 0.25 * tanh(demand_ratio - 1.0)`.
   - Even when supply equals or exceeds demand (`demand_ratio <= 1.0`, so `inflation <= 0.0`), low producer inventory (`avg_inv < 6`) generates up to `+30%` target price inflation per turn. Consequently, `wood` ratcheted from `\$1.00` to `\$12.68` and `furniture` pinned at the `\$50.00` hard cap by Turn 10.
2. **Household Raw-Material Hoarding & Buyer Queue Ordering in [`calculate_bid`](file:///Users/sli/Code/region_market.py#L115-L173) and [`clear_discriminatory`](file:///Users/sli/Code/region_market.py#L383-L554)**:
   - Every farmer (`output == Goods.food`) bids for up to `desired_wood = 10` units of wood as household stock.
   - [`clear_discriminatory`](file:///Users/sli/Code/region_market.py#L403-L408) orders buyers by `hungry_steps` for **all** goods, allowing 2,000 farmers to buy and hoard **21,071 units of `wood`** before `furniture` joiners can buy the `2` units of `wood` required as their production input. Starved of `wood`, `furniture` output collapsed from `176` units/turn (Turn 1) to `1–5` units/turn (Turns 10–30).
3. **Frozen Inventories After Career Switches in [`calculate_ask`](file:///Users/sli/Code/region_market.py#L176-L206) and [`clear_discriminatory`](file:///Users/sli/Code/region_market.py#L388-L395)**:
   - Only agents whose *current* `output == good` are permitted to post asks (`if agent.output != good: return 0`). When a woodcutter or joiner switches careers (or when a household accumulates excess raw materials), their inventory of `wood` or `furniture` is permanently locked out of the market.
4. **Hardcoded Three-Good Auction List in [`trade`](file:///Users/sli/Code/region_market.py#L741)**:
   - `goods_goods = [Goods.food, Goods.wood, Goods.furniture]` excludes pastoral and industrial goods (`wool`, `cloth`, `iron_ore`, `steel`, etc.) even when produced locally on the tile (e.g., `12–14` units/turn of `wool` from pasture plots had `0` sales and frozen prices).

---

## 2. Implementation Plan

### Phase 1: Symmetric Demand-Gated Scarcity & Glut Mean-Reversion
- **Files**: [`region_market.py`](file:///Users/sli/Code/region_market.py), [`price_trace.py`](file:///Users/sli/Code/price_trace.py), [`test_run_trace.py`](file:///Users/sli/Code/test_run_trace.py)
- **Changes**:
  - In [`update_price_ref`](file:///Users/sli/Code/region_market.py#L296-L364) and [`replay_reference`](file:///Users/sli/Code/price_trace.py#L10-L31):
    - Compute raw inventory deviation around `maxinv * 0.5`:
      $$\text{raw\_scarcity} = \text{clip}\!\left(1.0 - \frac{\text{avg\_inv}}{\max(0.1,\; 0.5 \cdot \text{maxinv})},\; -0.60,\; 1.0\right)$$
    - When $\text{raw\_scarcity} > 0$ (low producer inventory), gate positive scarcity pressure by excess demand:
      $$\text{demand\_gate} = \text{clip}\!\left(\frac{\text{demand\_ratio} - 0.90}{0.60},\; 0.0,\; 1.0\right), \quad \text{scarcity} = \text{raw\_scarcity} \cdot \text{demand\_gate}$$
      so a cleared or oversupplied market ($\text{demand\_ratio} \le 0.90$) never inflates from empty shelves alone.
    - When $\text{raw\_scarcity} < 0$ (inventory glut above `0.5 * maxinv`), gate negative scarcity (glut discount) by slack demand:
      $$\text{glut\_gate} = \text{clip}(1.2 - \text{demand\_ratio},\; 0.0,\; 1.0), \quad \text{scarcity} = \text{raw\_scarcity} \cdot \text{glut\_gate}$$
      so high unsold inventories actively pull prices down toward fundamental cost floors.
  - Keep [`replay_reference`](file:///Users/sli/Code/price_trace.py#L10-L31) in exact lockstep so all `market.reference.v1` causal trace events replay with 100% precision.

### Phase 2: Productive Input Priority, Household Reserve Caps & Inventory Liquidation
- **Files**: [`region_market.py`](file:///Users/sli/Code/region_market.py)
- **Changes**:
  - **Productive Input Priority in [`clear_discriminatory`](file:///Users/sli/Code/region_market.py#L403-L409)**:
    - Keep hunger-priority buyer ordering (`hungry_steps` descending) for `Goods.food`.
    - For non-food goods (`good != Goods.food`), sort buyers so **workshops/artisans requiring `good` as a recipe input** (`input_good(region, a) == good`) buy first, followed by inter-regional traders (`a.is_trader`), followed by household consumers.
  - **Working-Input Buffer vs. Household Reserve Cap in [`calculate_bid`](file:///Users/sli/Code/region_market.py#L153-L173)**:
    - Allow active producers whose recipe requires `good` (`input_good(region, agent) == good`) to bid up to `2` turns of input stock (`agent_recipe['numInput'] * 2 * (1 + num_employees)`), preventing 1-turn supply hiccups from halting `furniture` or `cloth` production.
    - Cap non-input household consumer bids for raw `Goods.wood` to a realistic domestic fuel/repair reserve (`2` units, or up to `4` for high `consumption_multiplier`), and `0` for purely industrial raw inputs (`iron_ore`, `coal`, `nitrates`, `wool`, `cotton`) by non-producers.
  - **Inventory Liquidation After Career Switches in [`calculate_ask`](file:///Users/sli/Code/region_market.py#L195-L206) and [`clear_discriminatory`](file:///Users/sli/Code/region_market.py#L388-L395)**:
    - Allow non-traders who no longer produce `good` (`agent.output != good`) to sell excess inventory above their personal reserve (`4` units for `food`, `2` units for `wood`, `1` unit for `furniture`, `0` for industrial intermediates).

### Phase 3: Dynamic Multi-Good Local Market Clearing
- **Files**: [`region_market.py`](file:///Users/sli/Code/region_market.py)
- **Changes**:
  - In [`trade`](file:///Users/sli/Code/region_market.py#L741), start with `[Goods.food, Goods.wood, Goods.furniture]` and dynamically append any locally tradable good `g` in `region.goods` (excluding `gov`, `none`, `transport`, and `import_only` goods) that has active local inventory, active producers, or active input demand on the tile.

### Phase 4: Verification & Causal Trace Replay Audit
- Run [`test_run_trace.py`](file:///Users/sli/Code/test_run_trace.py), [`test_food_security_recovery.py`](file:///Users/sli/Code/test_food_security_recovery.py), [`test_plunder_labor.py`](file:///Users/sli/Code/test_plunder_labor.py), and [`test_capitalist_propagation.py`](file:///Users/sli/Code/test_capitalist_propagation.py).
- Re-run the 50-turn `default_three_nation` (`seed=777`) trace benchmark and compare profession shares, `food`/`wood`/`furniture`/`wool` prices, production, sales, and inventories against the pre-fix trace.
