# Firm planner: complete-turn economic validation

**The stronger check does not establish economic superiority.** Twenty varied
operational decisions execute and reconcile, but active finishes below ordinary
policy in **17 cases** and ties in **3**, at manufacturing cost. Keep the
experiment off by default. Runtime changes through `cd5c916` are on
`feature/elite-operator-runner`; main is unchanged.

The earlier favorable run stopped after the second auction, omitted that turn's
payroll and used inconsistent price anchors. Its raw results are preserved in
[twenty_decisions_pre_economic_review.json](twenty_decisions_pre_economic_review.json).
They establish neither comparative profit nor planning quality.

## Twenty independently specified decisions

[twenty_decisions.json](twenty_decisions.json), schema 2, contains the current
paired active/ordinary results. Every pair starts from the same serialized
actors, inventories, liabilities, module state and RNG. Quotes and internal
market anchors are initialized together; later price discovery stays normal.

| Family | Cases | Initial choice tested |
| --- | ---: | --- |
| Limited cash | 5 | Buy one two-unit input batch and preserve current payroll/claims |
| More capacity or advance stocking | 5 | Buy 4, 6, 8, 8 or 12 input units for available work and funded demand |
| Existing inputs | 5 | Buy zero; starting stock covers the declared period's work |
| Decline new inputs | 5 | Buy zero because observed funding, material contribution, cash or a complete input batch is absent |

The named cases are independent conditions, not twenty random variations of one
successful example. The first three families actually produce and sell output
through normal engine handlers. Declining a purchase does not dismiss employees;
all active cases pay the full declared payroll, including idle work periods.

Representative observations (cash values rounded):

| Case | Initial input purchase | Active end net assets at cost | Ordinary end net assets at cost | Interpretation |
| --- | ---: | ---: | ---: | --- |
| `affordable_batch_1` | 2 | 22.82 | 25.82 | Avoids input credit, but loses a turn's productive labor relative to financed production |
| `capacity_batch_2_workers_4` | 8 | 73.61 | 73.61 | Stocks two batches for two workers; retains two output units at the terminal boundary |
| `existing_inputs_3` | 0 | 40.28 | 40.30 | Uses existing stock; small differences arise through actual market/financing effects |
| `negative_material_contribution` | 0 | 24.00 | 30.00 | Avoids loss-making materials, but retains wage contracts while ordinary policy dismisses workers |
| `incomplete_input_batch` | 0 | 8.00 | 8.00 | Neither policy can operate a complete batch; both still pay wages |

These are two- or three-turn controlled economies, not an unrestricted world
benchmark. `no_observed_demand` means no funded historical demand at the decision
point, not an externally enforced shutdown. Bank credit and income earned from
input sales can fund new buyers later; the current forecast misses such demand.
The tests preserve those unfavorable comparisons instead of removing them.

## Measurement and valuation

Each declared turn runs normal input/output auctions, corporate production,
payroll, wage-arrear settlement and cash obligations, then seals the cash
statement. The fixture explicitly enables only elite planning, the local market,
production and wages in the existing central gameplay flags. Other mechanisms
are held out; this is a complete declared production/supply turn, not a full
46-mechanism world turn. Market credit behavior remains the existing policy.

The result includes initial and terminal cash, bank deposits, inventory quantities,
bank principal, cash obligations and wage arrears. The independent test observer
values purchased inputs at actual recorded cost and manufactured output at direct
material plus paid production wages. Idle wages are expenses; unsold production
remains inventory, and selling it removes its cost. This observer never writes
simulation assets. A separate arithmetic check verifies that spending 4 on inputs
and 3 on production wages does not create profit merely by making inventory;
selling the output for 10 realizes a gain of 3.

The report also marks both policies' inventory at the same initial reference
prices. Neither manufacturing cost nor a reference quote guarantees liquidation
value. A baseline holding unsold output can have higher book net assets without
having realized that value in cash. Inventory, debt, realized receipts and both
valuation bases remain visible so the reader can distinguish them.

Forecast comparisons use the same completed-turn horizon, not the earlier
post-auction checkpoint. Actual outcomes are also marked using the forecast's
initial input/output prices and remaining buyer funding to expose forecast error.
For example, `affordable_batch_1` forecasts a terminal value of 10.10 and realizes
22.82 on that basis: prices are now initialized consistently, but the forecast
still substantially understates endogenous price/demand effects.

When ordinary policy cannot fund its purchases/payroll without borrowing, search
labels its comparison `ordinary_requires_financing_compared_with_idle`. It does
not claim that idle is the actual ordinary-policy outcome. The paired run executes
the real ordinary policy, including its credit and employment choices.

## Corrections made during this review

- Initialize fixture quotes and internal anchors together; remove the shared stale
  furniture anchor that had produced identical 35.11 receipts in the old check.
- Compare baseline and candidates after the same number of completed turns,
  including all payroll/dues in the horizon.
- Prevent an input commitment from spending proceeds of a later output clearing.
- Treat observed demand as a recurring estimate, limited by one shared buyer cash
  budget. Repeated turns do not replenish that cash magically.
- Consider whole future work batches when advance stocking can avoid a later
  cash constraint. The case buying 12 input units exercises this path.
- Store explicit one-turn wait/decline instructions in the existing active-plan
  owner. Their zero target replaces the ordinary input bid and wakes for review;
  it does not fall through into a bulk purchase or unnecessary input borrowing.
- Keep a multi-batch plan open until its remaining purchased inputs are processed
  and its final output is actually sold. Consuming input before producing the
  second batch can no longer mark the plan complete prematurely.

The implementation adds no hiring/firing policy or new live credit facility.
Source market, production, wages and claims still own all actual mutations.

## Validation and reproduction

**216 focused tests passed**, including the varied twenty-case comparison,
complete-turn off/shadow state and RNG equivalence, case-order reproducibility,
resource/cash statements,
source receipts, pending commitments, expiry/gates, hold serialization,
multi-batch completion and fresh-process active-plan recovery. Full checkpoint
continuation also passed for the default world and both authored scenarios.

Three older `tests.test_run_trace` failures remain documented from unchanged
main `1c6766c`: the missing `people` entry when turn is omitted in the withheld-
hours fixture, productive-practice versus zero-output event order, and a missing
zero-production link in the live-server fixture. This is not a claim that every
repository test passes. Raw validation logs remain local under
`/private/tmp/planner-econ-*`; ignored log files are not forced into Git.

```sh
ELITE_PLANNER_ACCEPTANCE_REPORT=planning/reports/elite_planner_acceptance/twenty_decisions.json \
PYTHONPATH=. MPLCONFIGDIR=/private/tmp/engineering-mpl \
venv/bin/python -m unittest tests.test_elite_plan_acceptance
```

This worktree uses `/Users/sli/Code/venv/bin/python`. The runtime never imports
these acceptance fixtures or writes the report. Settings remain in
`core/world_config.py`; `--elite-planning-mode off|shadow|active` defaults off.

Before broader rollout, address credit opportunity costs, workforce choices,
endogenous counterparty income/current demand and forecast calibration, then
measure longer complete-world runs. The current result is a more trustworthy
validation and several concrete correctness fixes, not a profitable-planner
certification.
