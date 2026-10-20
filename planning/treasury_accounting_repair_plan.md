# Unique public-account treasury aggregation

Date: 2026-10-19. Accounting repair allowed by Phase 0/3 of the causal trace
completion plan; keep it separate from trace-only changes.

The three-turn default diagnostic at commit `3cd24fa` used seeds 4242 for world,
terrain, and nations, with the current Voronoi topology (80 tiles, 3 nations).
It produced 112,924 rows / 6,451,692 compact bytes with three valid checkpoints.
Turn durations were 2.138, 2.407, and 2.244 seconds. Nine treasury reconciliations
had nonzero residuals, summing to 1,533.3758597259896 in absolute local-currency
values. These are diagnostic values, not a meaningful cross-currency economic
total. Source report: `tmp/trace_coverage_default_2026_10_19.json`.

Source audit found that `Nation.treasury()` deduplicates provincial cash in
one diagnostic subtotal but adds the shared government's cash, deposits, and
food once per tile to the displayed aggregate. It can also omit a distinct
provincial government from the aggregate when each tile has a separate
municipal government. These totals are used by AI and affordability gates.

1. Enumerate unique sovereign, provincial, and municipal governments under
   current territory. Classify shared governments at their highest tier.
2. Count each government's cash and food once, and each government/bank deposit
   account once. Include directly referenced government banks and owned tile
   and provincial banks without mutating money, goods, or account ledgers.
3. Retain the existing public report fields and add serializable account
   components for trace inspection. Component subtotals must sum to total cash,
   and cash plus unique deposits must equal the treasury total.
4. Test shared provinces, distinct tiers, repeated account references, deposits
   at multiple banks, same-named but distinct institutions, and read-only calls.
   Run fiscal, public-transfer, bond, UI serialization, and trace checks.
5. Repeat the diagnostic. Preserve any residual from missing operations; never
   insert a synthetic flow to make reconciliation pass.

Progress: implemented. Shared/distinct-tier, repeated-reference, multi-bank,
same-name, territorial-removal and read-only fixtures pass. The treasury,
federalism, construction funding, banking, public-transfer, web parity and
run-trace suites passed 86 tests. The repair changes reported/AI-visible
balances by removing duplication and including previously omitted distinct
provincial accounts. It does not pool these funds into sovereign cash or
change the scope of existing affordability gates.

The repeated three-turn diagnostic starts at 1,200 / 1,400 / 1,400 instead of
1,600 / 1,800 / 2,000 for the United States / China / Japan. Its 112,921 rows
occupy 6,452,658 compact bytes and verify all three checkpoints. Observed turn
durations were 3.036, 2.972, and 2.211 seconds, with 248,889,344 peak process RSS
bytes. This is a short correctness probe, not the Phase 6 benchmark gate.
Report: `tmp/trace_coverage_default_unique_treasury_2026_10_19.json`.

All nine treasury reconciliations still have residuals; their absolute
diagnostic sum is now 1,085.0122714212243 across local-currency values. Bank
closing snapshots and four final labor rollups also remain unexplained.
Continue auditing actual operations and sampling boundaries; the aggregation
repair does not manufacture a balancing flow or make a completeness claim.
