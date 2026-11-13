# Elite operator runner: first refactor step

Branch: `feature/elite-operator-runner`, based on main `1c6766c`.

## Change

The planner's five repeated machinery/frontier blocks now use one runner in
`economy/elite_operator_runner.py`. Immutable stage records hold the existing
operator IDs, action labels, return thresholds and cash gates. The runner uses
the existing TransformationGraph registry and operator callbacks.

The planner still owns its snapshots and event publication, passed as callbacks
to the runner. Operator effects and cash transfers remain in their existing
handlers. Supply investment remains between the machinery and frontier groups.

| Order | Stage | Minimum cash | Strict return threshold |
| ---: | --- | ---: | ---: |
| 1 | Repair machinery | Operator prerequisites | No valuation gate |
| 2 | Construct machinery | 60 | > 15 |
| 3 | Existing supply-control stage | Existing rules | Existing rules |
| 4 | Plantation labor gang | Operator prerequisites | > 10 |
| 5 | Procure captive labor | Operator prerequisites | > 15 |
| 6 | Frontier conquest | 50 | > 20 |

Construction records a rejected cash gate and exposes its return threshold only
after feasibility passes. Conquest below 50 cash skips evaluation evidence.
These existing distinctions are preserved. Each stage sees current state after
any prior unsuccessful execution; failed handlers are not assumed to roll back.
Execution stops at the first successful action.

This step leaves graph search, generic inventory transformations, lord operator
selection and duplicated valuation explanations unchanged. Sharing evaluation
results with trace explanations remains a separate follow-up.

## Size

Physical lines include comments, docstrings and nested functions.

| Code | Before | After |
| --- | ---: | ---: |
| capitalist_planner.py | 2,352 | 2,202 |
| _plan_and_execute_elite | 1,221 | 1,067 |
| elite_operator_runner.py | 0 | 80 |
| run_operator_stage | Repeated in five blocks | 47 |

The two runtime files together remove 70 net lines. The main routine remains
large; this is the shared operator-stage extraction, not the entire planner
modularization.

## Validation

93 focused tests passed, run in these groups using repository venv Python,
PYTHONPATH=., MPLCONFIGDIR=/private/tmp/engineering-mpl and dummy SDL audio/video:

- New runner contracts, elite planning traces and gameplay flags: 47 tests.
- Complete capitalist propagation suite: 18 tests.
- SupplyStrategyTests, SupplyProposalTests, the elite action cash journal
  contract and market auction suite: 21 tests.
- Complete triangular trade/luxury suite: 7 tests.

Three new regression tests cover strict threshold equality, failed repair
spending before construction/supply, and conquest's silent cash rejection.

An old/new differential against main 1c6766c matched all 720 combinations of
operator stage, cash boundary, valuation boundary, feasibility, execution
success and tracing. Results, actor state, full trace rows and callback counts
were identical. Ten additional cases used real machinery/frontier handlers
with tracing on/off and matched state and full traces. The session comparison
script is `/private/tmp/elite-operator-differential.py`.

The authored-scenario checkpoint test was also run on both branches. Its labor
scenario passed; the supply scenario failed on both branches with the same
kind of canonical graph difference: pathlib lazy cache fields (_tail_cached,
_str, _root, _drv) and consequent reference numbering. This pre-existing failure
is not counted among the 93 passes. Session logs are
`/private/tmp/elite-operator-checkpoint.log` and
`/private/tmp/elite-operator-main-checkpoint.log`.

Changed Python files parse and `git diff --check` passes.

## Follow-up: responsibility separation

The coordinator now delegates market purchases, lord transformations, capital
investment and inventory liquidation to explicit action modules. Activation,
supply strategy, voyage and legislation methods each have a single owner while
the existing bound method API remains available. A transient decision owns the
result and consolidates repeated stage-result merging. Snapshot/evidence and
public-account contracts have separate owners. Removed the unused 121-line
preflight snapshot; test guards still reject any accidental extra preflight.

At this commit monetary behavior and the old wrapper journal fallback are
unchanged. The next slice replaces that fallback with source-owned cash entries.
Validation: 59 action/trace/treasury/propagation/voyage tests and 47 runner/gate
checks pass. The 730 prior differential cases plus six capital/liquidation/lord
cases match original state and complete traces.

## Follow-up: source-owned cash journal

Removed the wrapper's inferred capitalist_action_cash adjustment. Direct luxury
sales, inventory liquidation, equity funding, operator fees, machinery payments,
frontier cash payouts, law petitions and voyage charges now record named payer
and recipient legs in their owning handler. CashDistribution matches explicit
funding debits to actual payouts, including company/owner splits and self-refunds;
it uses the existing state mutation API and does not infer counterparties from
an action's final net balance. Unsupported callbacks remain visibly unposted
rather than receiving fabricated journal entries.

Intentional cash-flow corrections covered by regression tests:
- Machinery repair material surcharges now reach a seller, treasury or refund
  recipient; the surcharge previously disappeared.
- Voyages without cargo or a producer to pay are rejected before charging.
- Voyage arrival tariffs settle only when a real investor and treasury exist;
  a missing side previously allowed money to disappear or be minted.

Nine source-accounting contracts cover split funding, absent recipients,
material costs, frontier payouts, equity, law fees, freight/tariffs, invalid
voyages and unjournaled custom callbacks. A combined 117-test run passed before
the last custom-callback guard was added; the full nine-test accounting suite
then passed. No bounded-search implementation or enablement is included.

## Completed prerequisite: coordinator, deduplication and accounting

The follow-up requested before bounded search is complete on the same feature
branch. The public planner API keeps explicit bindings to the single function
implementations; there are no copied forwarding implementations. Its transient
result context consolidates stage-result merging without adding persisted plans.

| Responsibility | Owner |
| --- | --- |
| Stage order and public entry points | capitalist_planner.py |
| Single-decision result and stage acceptance | elite_decision.py |
| Eligibility, novelty and cadence | elite_activation.py |
| Luxury selection / settlement / market delegation | elite_luxury.py |
| Input strategy and proposals | elite_supply.py |
| Political and voyage consideration | elite_legislation.py, elite_voyage.py |
| Lord operator selection and execution | elite_transformation.py |
| Sector ranking, expansion and incorporation | elite_investment.py |
| Buyer selection and inventory sale settlement | elite_liquidation.py |
| Ordered machinery/frontier protocol | elite_operator_runner.py |
| Named cash funding and payout legs | elite_cash.py |
| Shared machinery target selection | elite_machinery.py |
| Return arithmetic and its explanation | operator_valuation.py |
| Decision/operator observations and public contracts | elite_decision_trace.py, elite_treasury_trace.py |
| Registered effects and voyage/law payment sources | transformation_graph.py, triangular_trade.py, labor_laws.py |

Capitalist planner file: 2,202 -> 87 lines. Main decision function: 1,067 -> 23
lines. Public execution/observation wrapper: 78 -> 7 lines. Removed the unused
121-line preflight and write-only last-plan-turn cache. Runtime source across
all affected files is approximately 80 lines smaller, including the new cash
and valuation helpers; the primary gain is distinct ownership and fewer repeated
implementations, not deletion of required effects or trace evidence.

The supplier census and liquidation buyer scan now have one implementation for
traced and untraced execution. Machinery prerequisites, execution and evidence
share target selection. Generic and native return explanations use the same
calculation providers as estimates. The generic explanation now applies the
funded-demand cap and commercial-versus-prestige rule that actual scoring used
already. Custom return hooks remain supported and do not inherit stale native
explanations. Full self-refunds create no fictitious gross cash transaction.

Final verification: 151 focused tests passed in the combined regression run
(operator valuation, operator stages, source cash accounting, elite traces,
treasury traces, capitalist propagation, triangular trade, supply strategy /
actor statements, labor law traces and central gameplay gates). Five valuation
contracts include a fresh-process native callback/valuation roundtrip, custom
hook replacement and fractional-stock trace neutrality. All 810 sampled return
estimates exactly matched the pre-deduplication arithmetic.

The full live checkpoint test also failed on unchanged main 1c6766c with the
same pathlib lazy-cache fields / reference-number shift seen on this branch.
It is not counted as passing. Logs: /private/tmp/elite-refactor-checkpoint.log
and /private/tmp/elite-main-default-checkpoint.log. The focused fresh-process
operator checkpoint test passes; full-world canonical checkpoint validation
still needs its separate baseline oracle repair before bounded-search rollout.

The prior three intentional cash-flow corrections remain separately recorded
above. Gameplay flags, normal stage priorities, RNG policy and graph-search
activation are unchanged. Generic inventory input consumption/projection and
the bounded search itself remain the subsequent planned work.


## Production planner follow-through

The subsequent production/input-supply implementation is complete on the same
feature branch, with central off/shadow/active configuration and default off.
See [the implementation contract](multi_step_elite_planning.md) and
[the twenty-decision economic validation report](reports/elite_planner_acceptance/README.md).
The previously reported pathlib checkpoint comparison failure is corrected;
full default and authored-scenario continuation now passes. The older refactor
measurements above describe their named commits, before this new capability.
