# Economic validation of firm planning

Status: implemented and validated on `feature/elite-operator-runner`; main is
unchanged. See [the economic report](reports/elite_planner_acceptance/README.md). The original twenty-case check proved settlement and liquidity, not
superior net assets; it is retained as historical evidence, not the new gate.

## Contract

1. Initialize fixture quotes and internal market price anchors together. Keep
   normal subsequent price discovery. Assert initialization explicitly.
2. Compare active and ordinary policy from identical starting objects/RNG for
   a declared number of complete turns. Every measured turn includes market,
   production, payroll, arrears and cash obligations, followed by cash sealing.
   Buying nothing still incurs payroll while workers remain employed.
3. Evaluate search candidates and its baseline at the same completed-turn
   boundary. An unfunded ordinary-policy projection is a financing limitation,
   not proof that the candidate generates more wealth. Use a funded idle
   counterfactual where necessary and label that comparison explicitly.
4. Include cash, deposits, input/output stock at cost, bank principal, wage
   arrears and cash obligations. Also report inventory at common initial
   valuation prices, realized receipts and interest. Neither extra cash nor
   unsold output alone counts as profit. Quantify forecast error separately.
5. Measure exactly twenty independently specified decisions. Five cases each:
   one affordable batch; larger batch for greater available capacity/demand;
   wait because existing inputs cover work; decline new inputs because funded
   demand or contribution margin is absent. Include adverse price/funding
   conditions across the cases. Expected decisions must follow stated physical
   capacity, quantities and cash constraints, not seed-based policy branches.
6. Where the new planner chooses to wait/decline input buying, its zero target
   must replace the ordinary bid. A missing plan followed by an ordinary bulk
   purchase does not pass. Keep these short-lived instructions with the existing
   active-plan owner, obey gates/expiry, and preserve actual payroll/contracts.
7. Validate ordinary policy honestly: retain inventory and debt, record wins,
   ties and losses, and never require every active run to outperform baseline.
   No new hiring/firing, forecasting of future RNG, or synthetic settlement is
   introduced to manufacture favorable outcomes.

## Commits and gates

| Step | Deliverable | Evidence |
| --- | --- | --- |
| 1 | This plan and the original result's limitations | Clear measurement boundary and expected decisions |
| 2 | Consistent fixture prices and reusable complete-turn accounting helpers | Quote/anchor assertions; payroll/obligation and inventory/debt arithmetic tests |
| 3 | Correct terminal search comparison and explicit wait/decline input intent | Same horizon; no double count; zero bid actually honored; gates and expiry |
| 4 | Twenty varied paired decisions and regenerated JSON | Four decision classes, complete turns, real fills, accounting and balance sheets |
| 5 | Recovery/shadow/adverse regression and concise report | Off/shadow state+RNG match; restore/partial-fill checks; recorded limits and mixed outcomes |

The first two classes must exercise actual production and later market sales.
Waiting and declining input purchases are decisions too, with explicit reasons.
The test must not confuse declining a purchase with dismissing employees or
suspending their wage contracts. If results reveal a weakness outside this
scope, record it rather than change the fixture until all comparisons win.

Final evidence belongs in `planning/reports/elite_planner_acceptance/`, with raw
logs left local under the repository's existing ignore rule. Keep the experiment
off by default and the work committed on this feature branch.


## Results and interpretation

All twenty declared decisions execute with reconciled complete-turn accounting:
five single-batch purchases, five larger/prestock purchases, five waits and five
declined input purchases. They are decision-contract checks, not twenty proofs of
economic optimality. At manufacturing cost, active finishes below ordinary policy
in 17 cases and ties in 3; none shows a net-asset gain. Preserve that result.

The exercise corrected terminal timing, recurring demand under a shared buyer
cash budget, whole-batch prestocking candidates, explicit zero bids, and premature
plan completion while another purchased batch remained. Cash-only planning still
misses financing opportunities, endogenous buyer income and workforce changes.
Idle payroll remains a real expense; buying nothing does not cancel contracts.
The experiment stays off by default pending those broader modeling improvements.

Regression evidence: 216 focused tests passed; full default and authored-scenario
checkpoint continuation passed, including fresh-process recovery. Raw logs remain
local under `/private/tmp/planner-econ-*` in accordance with the log ignore rule.
