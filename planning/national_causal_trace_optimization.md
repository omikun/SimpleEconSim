# National causal trace optimization

Authorized 2026-10-27: implement direct bulk coverage, compact verified
inactivity certificates, shared census inputs, and national contribution
summaries. Preserve every recorded tax receipt, government expenditure,
transfer, trade and other real inflow/outflow, including offsetting flows.
Commit completed changes without pushing.

Completed 2026-10-27. See the
[implementation report](reports/national_causal_trace_optimization.md) and
[benchmark evidence](reports/national_causal_trace_optimization.json).

## Invariants

- Account writes, gross positive/negative flows, their ordering, source links,
  reconciliation, residuals and membership/currency changes remain inspectable.
- Missing evidence is unknown. Only a checked inactive/unchanged state may use
  a certificate. A zero net movement never proves inactivity.
- Historical tile/nation/turn/epoch selection, stable IDs, formula replay,
  fixed prefixes, independent seeking and save forks remain valid.
- National summaries preserve both directions, all regional contributions and
  explicit attribution gaps. Bounded AI packets show full totals plus selected
  sources; omitted detail remains available in the inspector.
- No economic rules, RNG draws or background AI generation change.

## Implementation

- [x] Capture standard unchanged observations directly into compact templates,
  avoiding full event dictionaries and repeated metadata freezing. Batch them
  with ordinary events and reconstruct the existing logical contract.
- [x] Encode verified empty price reconciliations and fixed/retained Gini
  bookkeeping as bounded, explicit rule certificates. Preserve nonempty writes,
  changed-to-zero values, refresh samples, source gaps and rule transitions.
  Empty closing disease censuses and empty tax-distribution calculations also
  qualify only under their exact checked rules; actual tax receipts do not.
- [x] Share repeated labor census evidence within independently seekable
  packets; resolve full original inputs before replay and inspection.
- [x] Add national metric contribution summaries, preserving regional changes,
  membership/coverage effects, reducer semantics and unexplained residuals.
  Add gross fiscal inflows/outflows by kind alongside existing treasury flows.
- [x] Feed national summaries to the on-demand explanation packet, prioritize
  material sources, retain bounded requests and state any omitted detail.
- [x] Validate exact logical reconstruction, source links, offsetting fiscal
  flows, missing baselines, inactive-to-active transitions, historical queries,
  corruption/forks, live continuation, state/RNG equivalence and performance.
- [x] Document measurements, limits and completed implementation; commit.

Use the current implementation at `053201b` as the comparison baseline. Keep
diagnostic switches for comparing template emission and summaries. Measure
turn time and storage separately from cold/warm inspector lookup latency.

## Validation-driven correction

Financial regression tests exposed an existing double count: both individual
medical public payment legs and the regional `public_healthcare_spending`
summary were classified as treasury flows. Preserve the summary and its source
links as `finance.public_healthcare_spending` observation; keep individual
payment/receipt flow events and all account writes. This corrects reconciliation
and gross totals without changing cash, treatment, eligibility or random draws.
The original failure reproduces with all optimization switches disabled.
