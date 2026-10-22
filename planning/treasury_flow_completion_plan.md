# Public-account flow coverage follow-up

Date: 2026-10-21. The bank closing probe explains all changed bank stocks but
leaves nine changed national treasury snapshots without a closing explanation.
The operation audit still has nonzero residuals.

1. Diagnose actual writes using government-account identities, existing bank
   and construction records, and the actor journal. Keep shared public accounts
   deduplicated. Preserve the current unconverted currency semantics.
2. Add missing settled flows: public construction debits/refunds, government
   deposit-interest receipts, automatic bank credit and ordinary repayment, and
   enclosure receipts. Explicitly suppress duplicate fiscal credit entries where
   the fiscal collector already records a signed flow and financing-gap link.
3. Verify actual cash/deposit changes against signed flows, including failed
   construction rollback and bank-funded construction, which have different
   national treasury effects. Do not interpret a deposit-to-cash withdrawal as
   public revenue.
4. Repeat default probes, inspect remaining residuals, and document unsupported
   paths. Sum reconciliation alone stays an audit; full causal closure requires
   ordered account continuity and membership evidence, not merely a zero net
   residual. Do not relabel treasury snapshots as explained from a matching sum.

Progress: steps 1–3 implemented and tested. Added missing $300 construction
debits, the initial enclosure charter receipt, individual government
deposit-interest receipts, and automatic (non-fiscal) bank borrowing/repayment.
Fiscal borrowing explicitly suppresses the automatic duplicate while retaining
its financing-gap cause. Per-write construction debits/refunds preserve existing
frozen-withdrawal and rollback behavior. Bank-funded public construction does
not become a public cash receipt.

Step 4 diagnostic: all nine national operation sums reconcile within 2.6e-13
per nation/turn in a fresh default three-turn seed-4242 run. All 144 changed
bank stock snapshots remain explained. The compact trace has 114,064 rows and
three verified checkpoints. Report:
`tmp/trace_coverage_default_treasury_flows_2026_10_21.json`.
The nine treasury snapshots deliberately remain source_missing pending ordered
public-account continuity and territorial/account membership closure.

Six dedicated public-flow tests cover automatic versus fiscal bank credit,
individual deposit interest and repayment, private credit exclusion, cash and
deposit construction funding, frozen withdrawals and failed rollback, enclosure
receipts, and domestic coupon/maturity bank closure. An additional bank test
covers bank-funded emergency food policy. The bank/public-flow/construction/
fiscal/public-transfer/enclosure/estate/FX suite passed 40 tests; recorder and
catalog checks passed 44 tests. A combined suite containing the GPU-heavy bond
UI test crashed in the native graphics layer; isolated non-UI suites passed.
The earlier isolated bond suite passed, but this is not a claim that every
combined graphics test arrangement is stable. Scenario/public-transfer coverage and persistent trace acceptance
remain separate gates in the overall completion plan.


2026-10-22 follow-up: ordered account closure is now implemented for the default
diagnostic. All nine treasury snapshots verify through account chains and stable
membership, independently of the flow sum. See
[the account closure plan](treasury_account_closure_plan.md) for implementation,
tests and the remaining direct-writer/composition gaps.
