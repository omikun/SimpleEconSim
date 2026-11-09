# Supply shocks, price recovery, and proposed pricing integration

Status: model comparison and proposal only, requested 2026-11-02. No game runtime
pricing behavior changed. Source observations refer to the current working tree,
which contains ongoing uncommitted economic changes.

## 1. Competitive analytical benchmark

For one good, one currency and one market, define:

    D(p) = A (p / p0)^(-epsilon)
    S(p) = min(K, B (p / c)^eta)

Here A is demand at reference unit p0, epsilon > 0 is demand elasticity,
K is available capacity, c > 0 is a unit-cost scale, and eta > 0 is supply
elasticity. This is a deliberately simplified competitive benchmark. Flow
production, offered inventories and delivery capacity must be separated in the
game; K is not total physical stock everywhere in the world.

Equating demand and unconstrained supply, then imposing capacity, gives:

    p_flexible = (A * p0^epsilon * c^eta / B)^(1 / (epsilon + eta))
    p_capacity = p0 * (A / K)^(1 / epsilon)
    p_star = max(p_flexible, p_capacity)

This assumes positive quantities and capacity. Zero-capacity markets ration;
they do not produce infinite actual transaction prices.

A temporary reduction in K raises p_star when capacity binds. Restoring every
primitive restores the original equilibrium. A higher persistent equilibrium
requires changed demand, costs, productivity, capacity, institutions or market
structure. A recovered production flow does not establish that inventories,
working capital, routes, or competition have recovered.

## 2. Iterative benchmark

With the equilibrium above recomputed each turn:

    gap = log(p_star / p_t)
    lambda = lambda_up if gap > 0 else lambda_down
    p_next = p_t * exp(lambda * gap)

Use 0 < lambda_down <= lambda_up <= 1. With fixed p_star this converges to the
same target. A smaller downward coefficient delays recovery but cannot alone
justify a permanently higher endpoint. The coefficients in the illustrative
comparison (.5 up, .1 down) are arbitrary, not estimates or proposed balance
defaults. All speeds must use the same game-time basis.

An alternative that avoids solving for p_star is excess-demand adjustment:

    log(p_next / p_t) = kappa * log(D(p_t) / S(p_t))

For the uncapped constant-elasticity example, local convergence requires
0 < kappa * (epsilon + eta) < 2; monotone convergence requires it <= 1.
Lagged supply, budgets, inventory and nonlinear caps change these conditions.
Clipping a move limits instability; it does not prove convergence.

## 3. What the game currently does

The authoritative local market is micro/region_market.py, not the older paths
in some historical planning documents.

* calculate_ask_price: local sellers quote around the prior reference, modified
  by inventory and hunger. Local costs are not an independent anchor in this
  quote formula. Quantity decisions elsewhere do consider cost and reserves.
* calculate_bid_limit: starts from the reference plus scarcity/hunger premiums;
  caps include cash, productive output net of direct payroll, household planned
  limits, and trader destination value. Thus willingness to pay is partly
  reference-relative, but not wholly unconstrained.
* clear_discriminatory: sorts offers, matches submitted buyer limits, and
  transfers cash and goods at the bid/ask midpoint. A reference is not an
  actual paid price or a universal posted transaction price.
* update_price_ref: starts with 0.25*tanh(bids/offers - 1), adds demand-gated
  inventory pressure, blends 25% toward the resulting multiplicative target,
  then blends with dated paid-price evidence. A sample's weight halves every
  three turns by default and expires after twelve turns. The pre-floor move
  is bounded to -8.75%/+12.5%; floors and the global reference cap of 50 apply
  afterward and can override that move bound.
* For abundance-enabled ordinary markets, the reference floor is 0.1. Otherwise
  it uses the recipe input-cost floor, or 1 for inputless goods. This is not a
  comprehensive wage, capital, freight and tax cost model.
* price_decay lowers an idle displayed quote by 5% under its threshold rule;
  it leaves _price_ref unchanged. This creates a separate reference/display
  state that should be evaluated in the proposal, not assumed to be stickiness.
* Transport still follows the separate legacy set_price route.

The existing rule is already iterative and permits price declines. Its
asymmetric bounds and inventory terms are not a calibrated model of firms'
repricing decisions. With responsive demand and offers it can return to the
old equilibrium. With neutral inventory, no paid samples, and bids/offers=1,
it holds the current reference, whatever its level. A balanced quantity ratio
alone supplies no independent evidence of a nominal target.

## 4. Controlled comparison already run

Reproduce from the repository root:

    venv/bin/python work/pricing-model-comparison/compare.py

This calls the current update_price_ref, with synthetic orders, neutral producer
inventories and no paid-price observations. It is not a full game simulation,
and fixed inventories deliberately prevent stock accumulation from contributing
to price recovery. The plotted fixed-order path illustrates the reference
formula's neutral point, not a complete stock-flow-consistent market.

Demand is 100*(p/10)^-1; elastic supply is min(K,100*(p/10)). Capacity falls
from 120 to 60 for turns 10-14, then returns to 120.

| Model | Turn 14 | Turn 30 | Turn 60 |
|---|---:|---:|---:|
| Instant competitive equilibrium | 16.667 | 10.000 | 10.000 |
| Current game reference, elastic orders | 11.686 | 10.219 | 10.004 |
| Asymmetric adjustment toward equilibrium | 16.403 | 10.960 | 10.039 |
| Current game reference, fixed order quantities | 11.959 | 11.959 | 11.959 |

These paths share the capacity shock but not adjustment speeds or endogenous
order rules. They demonstrate mechanisms, not a fit or ranking of realism.
Checkpoints, raw paths and chart are in work/pricing-model-comparison/.
Existing focused market checks: 11 tests passed using test_dated_market_prices
and test_market_auction.

## 5. Recommended integration design

Keep physical inventory, household budgets, seller ownership, and actual auction
settlement authoritative. Introduce proposed behavior behind a persisted pricing
mode, with the current mode as the comparison baseline.

### First: measure the cause before changing behavior

Extend the existing paired shock harness in economy/economic_shock_experiment.py.
Use matched seeds and pre-shock canonical state, a temporary physical shock,
and a longer recovery window. Compare each shocked run with its contemporaneous
unshocked control, not just its own pre-shock nominal price. Run a frozen-demand/
cost diagnostic and a fully endogenous economy separately.

Record reference and paid VWAP separately, with coverage/no-sale flags, offered
units, funded bids, desired but unfunded needs, production, inventories including
transit, capacity utilization, payroll, input replacement costs, actual receipts,
entry/exit, and routes. Never count an unfunded meal need as a funded order.
Report residual price premium, sold quantities, recovery half-time, costs and
markups where a valid cost denominator exists.

### Second: give local seller offers an independent economic basis

Prototype seller-level pricing in calculate_ask_price; preserve the auction.
Track a firm's prior ask, current replacement/avoidable costs and inventory,
and its observed sales and unfilled offers. Do not use prior reference times
a multiplier as the only economic value signal. Test candidate asks against
the seller's estimated residual demand, competitors and accessible imports.

Conceptually choose:

    argmax_p [p * expected_sales_i(p)
              - avoidable_cost_i(expected_sales_i(p))
              - expected_inventory_carry_cost_i(p)
              - repricing_cost_i(log(p / previous_ask_i))]

For production-and-sale decisions, avoidable costs include the cost of new units;
existing inventory acquisition cost is sunk. Do not impose historical unit cost
or full average cost as an absolute minimum sale price. Liquidity needs and
liquidation can justify below-cost sales. Estimate expected sales separately
from household physical need; honor buyer cash and substitute goods.

Different repricing penalties can slow cuts relative to increases. Strong
competition makes retaining an inflated ask costly through lost sales. Weak
competition may support a persistent markup, but concentration alone does not
identify that markup; demonstrate it through choice and outcomes. Avoid charging
fictional cash fees unless an actual resource/payment mechanism is implemented.

Use the analytical target model as a benchmark and optional shadow diagnostic.
An aggregate cost-plus target with a sticky coefficient is a cheaper prototype,
but it does not establish market power or uniquely determine a competitive
equilibrium. Do not label that shortcut an emergent firm-pricing model.

### Third: keep reference updates and trace semantics consistent

Use fresh settled prices for reference evidence, distinguish no trades from
zero prices, and address idle quote/reference divergence deliberately. Review
buyer reservation values as well as seller asks so both sides do not simply
inherit the same prior quote. Update trace/price_trace.py and version changed
formula IDs; historical recorded formulas must continue to replay unchanged.
Persist any new seller state and mode. Apply food updates once after both
sessions, and explicitly decide whether transport remains a separate market.

### Acceptance experiments

1. Temporary capacity shock, primitives restored, competitive access: prices
   return close to the matched control over a sufficiently long recovery.
2. Same shock with slow downward repricing: longer recovery, same endpoint.
3. Capacity restored but wages/input replacement costs remain elevated: any
   persistent premium is linked to measured costs and quantities.
4. Costs restored, weak seller competition: persistent margins require lost-sales
   incentives that support them; restoring competitor access reduces the premium.
5. Inventory glut, empty market, zero capacity, unaffordable food, and blocked
   imports: no phantom sales, duplicated units, cash creation or false VWAP.
6. Under each supported mode, conservation and trace replay remain exact; assess
   quantities, deprivation, entry and producer viability alongside prices.

No experimental pricing mode is implemented by this proposal.
