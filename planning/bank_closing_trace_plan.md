# Bank closing-stock causal coverage

Date: 2026-10-19. The default three-turn probe after labor closure has changed
snapshot gaps only for bank capital, deposits, liabilities, equity, and national
treasury. Per-tile bank-equity histories are sampled during local turns, while
the shared bank can change later in another tile or world/province phase.

1. Register each unique bank once per trace with starting balances and current
   tile aliases. Use trace-local institution IDs; shared-bank tiles must not
   create duplicate physical banks or operations.
2. Capture explicit capital/deposit/liability balances before and after real
   mutations in loan payment, lending, deposit, withdrawal, deposit interest,
   sovereign write-down, recapitalization and bail-in paths. Keep existing
   financial rules and RNG behavior. Record operation kind, actor, quantitative
   inputs, and links to existing transfer records where available.
3. Audit direct external balance writers: construction/capital transfers,
   frontier founding, FX floats, estate/debt/default resolution, and scenario
   effects. Add probes at their actual writes; mark any unsupported writer.
4. At turn close replay each bank's opening plus ordered recorded transitions.
   Check transition continuity and closing residuals by component. Emit exact
   closing calculations only for reconciled components. Missing mutations must
   produce explicit gap audits rather than a forced balance.
5. Link tile closing-stock snapshots to the registered bank's closing records.
   Give the earlier legacy equity-history calculation its own history-field
   subject so it cannot masquerade as an end-of-world-turn bank balance.
6. Verify shared aliases, state/RNG parity, deposits/withdrawals, loan principal
   and interest, blocked credit, and deliberately unrecorded mutations. Repeat
   the default probe and retain remaining treasury or bank residuals honestly.

Progress (2026-10-21): implemented registration, core methods, world closing,
strict replay/continuity checks, tile aliases, and external writers in
construction/policy funding, frontier subscriptions, FX floats, estate
loss/recapitalization/debt inheritance, and domestic bond coupons. Fresh
zero-capital provincial bank initialization is a registration starting condition,
not a runtime mutation. Existing coupon allocation rules are preserved even
when several tile entries refer to the same bank.

Eight dedicated tests cover shared aliases, distinct institutions, repeated
closes, next-turn openings, tracing/RNG parity, estate loss allocation, omitted
writes and offsetting omitted writes. Local bank-equity history has a distinct
history-field subject. Closing clears stale local stock evidence before
publishing validated aliases. A three-turn default probe explains all 144 changed
bank stock snapshots; all three checkpoints verify. This is a correctness
probe, not the full Phase 6 acceptance/performance run. National treasury operation reconciliation is a
separate follow-up; bank closing arithmetic cannot prove a missing public
cash transfer.
