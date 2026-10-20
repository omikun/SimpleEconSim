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

Progress: all five steps are implemented. The broader innovation, trace,
metric-catalog, web parity, infrastructure, fertilizer, and two innovation
client checks passed 95 tests; the final core innovation/trace/catalog run
passed 54 tests. The discovery journal is inventoried against multiple metric
sources. National trace context survives loss of all territory, and source
knowledge and bounty links remain valid across turns and snapshots.

The audit also found that catalog `production_modifiers` currently have no
production-code consumer. Trace unlocks label these as declared catalog
bonuses, rather than attributing realized output changes to them. Bounty
affordability uses the aggregate national treasury while the debit uses only
sovereign cash; traces preserve and expose a negative cash balance when that
occurs. An empty capital removes the prize with no recipients; the unpaid
escrow remainder is recorded explicitly. Gameplay/accounting changes to these
rules are separate work.
