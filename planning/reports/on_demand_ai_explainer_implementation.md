# On-demand AI stat explainer implementation

Date: 2026-10-26

Plan: [On-demand AI stat explanations and historical parallels](../on_demand_ai_stat_explainer_plan.md)

## Delivered behavior

The game can generate an AI explanation only after a deliberate explainer
request. Web controls support click, keyboard, touch, and a deliberate mouse
hover. Native controls support click/hover and an F12 metric chooser; F10 retains
its existing settings behavior. Both clients immediately show a loading drawer
and remain responsive while the requested work runs.

The shared service builds bounded evidence from a published trace boundary,
preserves verification levels and gaps, retrieves reviewed historical material,
requests a strict structured model response, validates its references, and
caches the completed report. A general chooser exposes all 388 catalogued
metric IDs; a missing record or missing numeric baseline receives an explicit
unavailable/gap state. No AI handler needs to be added for each individual metric.

Requests are deduplicated. Later turns and changes in affordability do not
force regeneration of a cached immutable tick report. Explicit evidence
boundaries remain part of cache identity. A separate current-state check handles
action availability. One worker, a four-job capacity, deadlines, event/input
limits, and bounded report retention prevent unbounded work.

Possible future mechanics appear in a dedicated **not implemented** section,
with unmet need, known-capability gap, proposed behavior, tradeoffs, acceptance
criteria, and provenance. Validated proposals are atomically logged under
`planning/potential_future_mechanisms/`. Repeated capability IDs merge occurrence
records and preserve reviewer status/notes. Failed planning writes are visible
and can be retried locally without a model call. No generated design is executed
or automatically scheduled for implementation.

The runtime model is configured through `COC_AI_EXPLAINER`, `COC_AI_MODEL`, and
`OPENAI_API_KEY`. See [configuration and usage](../../docs/ai_stat_explainer.md).

## Verification

| Check | Result |
| --- | --- |
| Focused explainer suite, including backend, desktop, seeded simulation, checkpoint exclusion, and persistence | 26 tests pass |
| Existing trace reader/codec/audit/command suite (`test_trace*.py`) | 19 tests pass |
| Existing desktop chart binding/replay suite | 19 tests pass |
| Existing simulation checkpoint continuation/recovery suite | 4 tests pass |
| Existing web-server suite | 48 pass; one independently reproduced baseline Gini-test error |
| Playwright desktop/touch explainer interaction suite | Pass |
| Python compilation, JavaScript syntax, Git whitespace checks | Pass |

The browser suite checks a dormant interface, keyboard focus and short hover
making no requests, deliberate hover, click deduplication, loading, cached
reopening, planning-log retry, action availability review, execution only after
an explicit Apply click, cancellation after a world change, chooser behavior,
and mobile layout. Desktop tests render the result/proposal drawer without a
GUI display and verify reset handling and shortcut behavior.

The live simulation smoke uses seed 4243 and the labor-frontier scenario for
three completed turns. It requests treasury, population, national food price,
and unrest reports using a fixture provider. It confirms:

- Zero provider calls during unrequested turns.
- Identical canonical world-state digest before/after requested reports.
- Identical sampled metrics and Python/NumPy random-number state.
- Unchanged authoritative trace count and digest.

One measured fixture run completed requested reports in approximately 0.27 s
for treasury and 0.01–0.07 s for the other three. These timings measure local
assembly, fixture response, and validation; **they are not live model latency**.
The generated diagnostic is `tmp/ai-explainer-live-smoke.json`.

Visual QA inspected `tmp/ai-explainer-loading.png`,
`tmp/ai-explainer-result.png`, `tmp/ai-explainer-mobile.png`, and
`tmp/ai-explainer-desktop.png`. These are local diagnostics, not tracked assets.

## Existing regression-suite issue

`test_food_cash_gini_chart_point_has_a_trace_record` in
`tests/test_web_server.py` raises `KeyError: replay_matches` when it reads a
Gini calculation's inputs. The same test fails identically with the unmodified
HEAD version of `trace/trace_index.py` loaded into the test process. No Gini
writer, Gini formula, or Gini test was changed for this feature. This pre-existing
test/record-contract mismatch remains separate from the explainer change.

## Integration repairs

Two trace-reader defects surfaced during verification and were fixed:

- A fresh indexed reader measured file size before its same-process buffered
  writer published, producing a stale boundary and a torn-tail error. Identity
  reading/publication now precedes size measurement.
- The live-writer weak-reference registry used a non-reentrant lock even though
  garbage collection could invoke a writer finalizer and re-enter registry
  cleanup. A reentrant lock prevents that deadlock.

The simulation checkpoint service exclusion list now includes `explanations`.
Runtime workers, locks, configuration, and credentials are recreated from the
current environment instead of being included in serialized gameplay globals.
Checkpoint continuation and recovery tests pass after this change.

## Explicit release limits

- API credentials and a model were not configured in this workspace. The
  Responses transport is implemented and mock-tested; live model prose quality,
  latency, and billing were not tested. AI stays disabled until configured.
- The reviewed historical library starts with four episodes: Irish food relief,
  Egyptian debt revenue controls, public-health administration, and factory
  working hours. No strong match produces an honest omission.
- The mechanics catalog is intentionally conservative and explicitly incomplete.
  It covers web granary/workday and native provincial health-program/granary
  controls. The native provincial program's current handler records spending
  and an announcement; the catalog does not claim that this proves a health
  benefit. Future proposals require review against the wider game code.
- Chart transformations, moving windows, and components retain their context,
  but AI prose explains raw recorded turn boundaries. The UI explicitly labels
  that scope and the deterministic chart inspector retains its detailed replay.
- Automated schema/reference validation cannot establish the truth of every
  sentence. Evidence levels, limits, and original source links remain available.

These limits are reflected in the updated plan and player documentation rather
than being presented as verified capabilities.
