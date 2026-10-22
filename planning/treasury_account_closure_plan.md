# Ordered public-account stock closure

Date: 2026-10-22. Implements the next step after
[public flow sum coverage](treasury_flow_completion_plan.md).

## Completion rule

A matching national flow sum is insufficient. A treasury snapshot is explained
only if the same public accounts and territory are present, its opening total
matches their opening balances, every recorded before/after transition is
continuous, and their closing balances sum to the independently observed total.
Missing intermediate writes, even offsetting writes, stay visible as audits.

## Implemented

1. Extracted `Nation._treasury_entities()` from the existing report collector.
   Reporting and tracing now enumerate the same unique government objects and
   bank references. Existing cash, deposit, food and currency semantics are
   unchanged. Empty deposit accounts are included in the trace inventory so a
   zero-to-positive balance has an explicit opening.
2. Added `TreasuryTraceBook` with trace-local public account IDs and references
   to the physical bank IDs already used by the bank ledger. Setup observations
   establish starting balances. Turn boundaries retain prior observed closes
   and membership; repeated closing reports retain the original turn opening.
3. Probed actual writes in bank credit, deposits, withdrawals, ordinary repayment,
   individual deposit interest, statutory bail-ins, fiscal debt service and tax
   allocations, construction debits/refunds, enclosure fees, government food
   purchases, national food-relief grants, government cash-transfer methods,
   estate probate cash/deposits, and estate bank recapitalization. Each probe
   takes its before image at the actual mutation. Internal cash/deposit moves
   have separate component records sharing an operation ID, not public revenue.
4. Added pure replay for individual account chains and national account sums.
   A failed component chain prevents national calculation coverage. Account or
   territorial membership changes remain audits with entered/departed account
   IDs and previous/current territory; unsupported account inventories are
   explicitly unavailable. No forced balancing entries are created.
5. Connected world setup, turn boundaries and final snapshots. The existing
   signed-flow reconciliation remains a separate audit. Coverage reports now
   distinguish `_treasury_account_closure` from `_treasury_reconciliation`.
   Existing web, desktop and CLI trace readers can inspect the new typed records
   and their cause IDs; no new player action is required.

## Verification

- Ten dedicated tests cover ordered cash/deposit movements, internal grants,
  shared accounts, physical bank ID references, next-turn and repeated closes,
  equal-and-opposite missing public transfers, offsetting missing writes around
  a recorded operation, bank/territory membership changes, statutory bail-in,
  frozen estate probate, compact checkpoint verification, coverage labels and
  trace-on/off state and RNG parity.
- The public/bank/fiscal/food-response/government/estate/construction/enclosure/
  emergency-food suites passed 78 tests. Recorder, catalog and web parity
  suites passed 68 tests. Final focused closure/fiscal/food-response checks
  passed 31 tests after tightening provenance assertions.
- A fresh three-turn default world (all three seeds 4242, 80 tiles, three nations,
  default autoplay settings) verifies all nine national account closures and
  their nine changed treasury snapshots. All 144 changed bank stock snapshots
  remain explained. The compact trace has three verified checkpoints. Report:
  `tmp/trace_coverage_default_treasury_chains_2026_10_22.json`.

Inspect national closures and then follow an account's source event IDs:

```bash
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --turn 2 --entity 'nation:China' --kind treasury_account_closure --verify
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --turn 2 --metric finance.public_account_balance
```

## Remaining limits

This closes the default diagnostic, not every scenario or every possible public
writer. Direct writes in military upkeep, banking-policy rescue, sovereign bond
cash settlements, political actions, scenario-specific public transfers, and
some manual transfer actions still need individual account probes. Their
existing signed-flow/transfer records are retained; a changed account with no
stock probe produces a chain gap. Territory/account changes are reported but
are not yet promoted to verified composition bridges. A later turn may use the
observed closing balance as its starting observation without claiming the
previous unexplained change has been repaired.

Long-run performance, trace persistence/index/recovery gates and full scenario
acceptance remain in the overall causal coverage plan. These short diagnostics
do not prove that every upstream decision or displayed metric is fully covered.
