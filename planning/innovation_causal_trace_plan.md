# Innovation causal trace implementation

Date: 2026-10-19. Follow-up to Phase 4 of the causal trace completion plan.
Preserve research rules, random draws, iteration order, and monetary outcomes.

1. Record domain experience where learning is added. Capture the exact last
   production/export/tax samples and territory membership used, units,
   coefficients, fixed increments, opening XP, and closing XP. Preserve the
   existing finance rule's `tax_revenue_log` lookup and military rule's
   unit-count proxy; label missing tax sources and proxy units explicitly.
2. Record real research gates in catalog order: known technology, prerequisites,
   resources, XP threshold, bounty multiplier, breakthrough chance, and the
   existing random draw. Capture built-in bottleneck inputs during their real
   evaluation. Link learning, pressure, successful discovery, and unlock state.
   Custom callbacks with no input evidence remain recorded observations.
3. Record directed trade-pair diffusion in its existing order, including source
   and destination technology sets, actual export-value samples, trade pact,
   progress increment, prior/closing progress, and adoption. Preserve positive
   baseline diffusion at zero trade and the current absence of resource or
   prerequisite checks in this path; expose both rules.
4. Record bounty offer gates, treasury debit, escrow reservation, discovery
   multiplier, per-agent payout, and escrow removal. Identify cash/deposit
   affordability versus the actual cash-only debit. If discovery removes an
   escrow with no capital residents, record the unpaid remainder explicitly.
5. Register metrics, pure formula replay, and relevant snapshots. Verify exact
   XP increments, all built-in pressure branches, rejected research gates,
   successful/failed rolls, diffusion/adoption, bounty transfers and no-recipient
   behavior. Compare trace-on/off state, RNG state, callback counts, and event
   order. Run existing innovation-facing tests and document results.

Progress: steps 1–3 are implemented, along with metric registration, formula
replay, read-only snapshots, and focused state/RNG/callback parity checks.
The combined innovation, metric-catalog, run-trace, and two existing innovation
client checks passed 52 tests. Step 4 (bounty funding and payouts) remains open.
The current
`discovery_log` is an event journal spanning bounty offers, discoveries, bounty
awards, and diffusion. It needs multiple registered metrics rather than a
single scalar-history mapping.
