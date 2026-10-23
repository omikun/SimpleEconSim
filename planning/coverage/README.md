# Gap register: discovery, review and runtime evidence

`causal_gap_inventory.py` discovers financial-write candidates, declared metrics,
history fields and literal UI metric references without constructing a world.
The scanner is a review aid; it does not establish public ownership or whether a
caller is active. In particular, `Nation.capital` can be a geographic capital,
private cash writes can appear in public-payment functions, and an unused history
can share a name with a displayed series.

Regenerate and check:

```bash
venv/bin/python causal_gap_inventory.py --check --json tmp/causal_gap_inventory.json --markdown planning/coverage/financial_gap_register.md
```

- `financial_write_baseline.json` records candidate IDs, including unreviewed
  ones. Tests detect new/removed/changed writes. IDs include mutation syntax,
  enclosing function and `if` eligibility guards, but not source line numbers.
- `reviewed_financial_writers.json` contains explicit source reviews and their
  fixture evidence. Writer, formula, links, closure and UI have independent
  statuses. A fixture for one conditional branch does not verify other branches.
- `financial_gap_register.md` is the generated summary. The generated JSON lists
  every candidate, unit/timing metadata where reviewed, catalog metric,
  history reference and literal UI reference candidate.

When a mutation changes, inspect the new/removed entries, classify it, update
its review or leave an explicit review task, and deliberately update the baseline.
Do not automatically promote new candidates or catalog declarations to verified
coverage. Guard detection does not perform interprocedural alias analysis or
prove every loop/caller condition. Dictionary aliases and indirect mutation
helpers still require review. Scenario call-path classifications and verified UI
bindings remain open until their fixtures and sampling semantics are checked.

## Current execution slice (2026-10-22)

Update 2026-10-23: 507 candidates, 80 source reviews and 427 pending reviews;
384 metric declarations and 88 history fields. Two history-method callsites are
listed separately rather than being counted as stored series. A separate literal scan locates
363 writer IDs in probe inputs; this does not establish their execution or
semantic closure. Literal UI references include `web_client/` directly.
The dated findings below remain historical evidence for the earlier slice.

- 508 financial-write candidates: 11 source-reviewed military/medical writes,
  497 awaiting classification. There are 381 metric declarations and 89 history
fields; these counts are discovery totals, not coverage percentages.
- Runtime probes cover full/partial military payroll, ration procurement,
  public/private treatment, government provider receipts and self-refunds.
  Existing payment records link to returned public-account write IDs. A medical
  treatment/self-refund shares a semantic operation ID across its two writes.
- Ration cash settlement previously lacked a signed national treasury-flow row;
  it now has one linked to the existing payment. Private medical fees paid to
  a public provider also record the actual treasury receipt. No gameplay money
  movement was changed and no duplicate payroll/public-care outflow was added.
- Five dedicated integration tests cover full and frozen/partial/unfunded payroll,
  procurement, five medical funding/provider cases, state/RNG parity, checkpoint
  verification and a deliberately omitted self-refund probe. A zero national
  delta still fails account closure when the refund's intermediate write is missing.
- The focused inventory/military/medical/public-account suites passed 47 tests;
  recorder and web parity passed 63 tests. Static inventory checking, Python
  compilation and `git diff --check` passed.
- A fresh default three-turn seed-4242 world still verifies all nine treasury
  closures and all 144 changed bank stocks with three valid checkpoints:
  `tmp/trace_coverage_default_military_medical_2026_10_22.json`.
  This probe does not exercise war or prove long-run/scenario acceptance.

Phase 0's full active-path, history and UI classification gate remains open.
Phase 1's next financial slices are bank rescue, sovereign cash settlements,
construction progress and remaining estate paths. The registry provides a queue
for those reviews; the first audited military/medical subset is implemented.
