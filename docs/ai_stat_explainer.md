# On-demand AI stat explainer

The explainer reads a selected turn's causal trace, writes a short narrative,
adds a sourced historical comparison when a useful one is available, and
connects the explanation to real game actions. If known actions do not address
the problem, it can suggest a separately labeled future mechanic and log that
design for review.

## Enable generation

Set these variables in the environment that launches the game or web server:

```sh
export COC_AI_EXPLAINER=1
export COC_AI_MODEL='<your Responses API model with Structured Outputs support>'
export OPENAI_API_KEY='<your API key>'
```

Restart the game/server after configuring them. Credentials stay on the Python
side; the browser does not receive the key. With the feature disabled or its
configuration incomplete, the panel explains what is missing and the ordinary
recorded-evidence inspector remains usable. The model is deliberately an explicit
configuration choice rather than a silently selected default.

No API request is made when importing the feature, advancing turns, rendering
charts, opening ordinary dashboards, or loading a save. Each deliberate AI
request can incur provider usage. Closing a panel cancels queued work when no
other viewer needs it; an already dispatched API request may still finish.

## Request an explanation

**Web:** Open a chart/price evidence detail and click **Explain with AI**. A
deliberate mouse hover over that specific control also requests it after a
short dwell. Keyboard activation and touch taps work. The **AI: explain a stat**
launcher opens a searchable metric chooser; choosing a metric alone does not
generate anything. Specify the selected entity, turn, and any good, disease, or
class-group dimension before pressing **Generate explanation**. The chooser
also contains the hover preference.

**Desktop:** Click a chart point or open an F11 evidence record, then use
**Explain with AI** at the bottom right. F12 opens the general stat chooser.
The chooser lists **only stats recorded for its selected entity and turn**,
with goods, professions, diseases, and other dimensions included automatically.
Type to filter (for example `goods.price` or `good=food`), use Up/Down to select,
and click a stat or press Enter to request its explanation. The first local
index build can take several seconds; **Reading recorded stats…** keeps the
drawer usable without calling the model.

Click an uncovered map tile to switch the chooser to that tile, or click
**Change tile / nation**, type its name/number, and select a match. It is not
limited to `c0`. Tab/Shift+Tab also cycle entities. Left/Right or the turn buttons
change the selected turn; Refresh reads newly published records. Turn 0 and
entities without matching records show an explicit empty state.

Clicking a different map tile while a narrative is open returns to that tile's
stat chooser; it never automatically generates another narrative. **Choose
another stat / tile** also returns to the picker. F12 replaces an open F11
inspector, so F11 cannot swallow map clicks behind it. Escape closes the drawer.
The chooser has a hover toggle. Scroll inside the drawer to read long
explanations and source links.

The [desktop correction report](../planning/reports/ai_explainer_trace_selection_and_turn_performance.md)
documents the missing-trace and tile-selection fixes, measured turn speedups,
and remaining trace-recording costs on the default 1,000-region map.

New traces use [packed storage and checked unchanged-stat coverage](trace_storage.md).
Historical selections still expose the same observed values and causal source
IDs, including unchanged stats; coverage does not silently fill missing turns.

The loading screen remains visible through evidence collection, local history
matching, model generation, and response validation. It shows the selected stat,
entity, and turn, and allows cancellation. Playing can continue while it works.
Pin a hover-opened panel by clicking inside it. Results remain tied to their
original selection; resetting the world closes stale panels.

## Evidence and advice

Exact values, units, source IDs, verification labels, historical facts/citations,
and known action metadata come from game records and the reviewed local content
library. Model prose is qualitative. The application validates its schema and
references and rejects unsupported figures or invented action IDs. These checks
cannot guarantee that every semantic claim in a generated sentence is correct;
the evidence and limitations remain visible for inspection.

Ordinary turn requests use the first recorded tick snapshot. The desktop event
inspector can request an explicit trace epoch to explain a between-turn command
separately. National chart aggregates without snapshots use the preceding turn's
aggregate as the opening observation when available. Missing baseline values
produce an unavailable delta, not an assumed zero.

Transformed/component/windowed charts retain their display context. This release
explains **raw recorded turn values** and labels that distinction explicitly;
it does not attribute a moving-average or component delta to a raw total. Use the
existing deterministic chart inspector for its detailed component/window replay.
Bounded source traversal and summarized large account records are also labeled
as partial evidence, with original records available in the inspector.

The initial reviewed historical library covers Irish food relief, Egyptian debt
revenue controls, public-health administration, and factory working hours. Source
claims distinguish documented responses from unverified forecasts of success.
Matching prioritizes the causal mechanism and then geographic relevance. A
missing strong parallel is a valid result; the model does not research or invent
a historical event at runtime.

The mechanics catalog currently describes web granary relief and the Ten-Hour
Act, plus the desktop provincial health initiative and granary relief. The
current health-initiative handler records spending and an announcement; the
catalog does not claim a demonstrated treatment/sanitation improvement from it.
Other policies and scenario
mechanics exist. Future designs therefore remain provisional catalog gaps until
reviewed against current code. An existing action that is merely unaffordable or
locked is not a future mechanic.

Web **Review action** refreshes local availability without generating a new
narrative, then shows the implemented command's prerequisites/effect. Only an
additional explicit **Apply** click submits that normal game command; the model
never performs it. Desktop **Open policies** navigates to the existing controls.
Current-state checks do not rewrite the original historical advice.

## Future-mechanic planning records

The **Possible future mechanic — not implemented** section contains an unmet
need, the gap in known actions, a concrete design, tradeoffs, and acceptance
criteria. It never has an execution control. Validated proposals are recorded in
`planning/potential_future_mechanisms/*.json` with status `proposed` and run/turn/
stat/evidence provenance. Equivalent capability IDs in the same client/scenario
merge occurrences; cache hits do not duplicate them. Existing reviewer status,
notes, and proposal content are preserved.

See [the review guide](../planning/potential_future_mechanisms.md). A proposal
does not authorize or schedule implementation. If the planning folder is
unwritable, the explanation still appears and **Retry planning log** retries only
the local write, without another model request.

## Local storage and limits

- Validated explanation cache: `tmp/ai_explanations/`, capped at 256 reports.
- Planning log: `planning/potential_future_mechanisms/`; these are reviewable
  project artifacts, separate from simulation traces.
- One model worker, up to four active/queued distinct requests.
- Provider timeout: 45 seconds; request deadline checked between stages: 65 seconds.
- At most 64 source events, 48 initial metric records, and four upstream levels.
  Oversized nested books/issue lists are summarized; oversize packets fail safely.
- No automatic provider retries. A failure offers an explicit Retry control.
- Cache keys include run/branch, boundary, subject dimensions, display context,
  action context, model, and packet/schema/prompt/history/catalog versions.

No trace file is modified by explanation generation. The provider receives only
the bounded evidence/context packet, not the full save or complete trace. Cache
and planning outputs contain the explanatory material and its source identifiers.

## Verification

```sh
MPLCONFIGDIR=/private/tmp/coc-ai-mpl venv/bin/python -m unittest discover -s tests -p 'test_ai_explain*.py' -v
MPLCONFIGDIR=/private/tmp/coc-ai-mpl venv/bin/python -m unittest discover -s tests -p 'test_trace*.py' -v
```

`tests/test_ai_explainer_browser.js` uses Playwright/Chrome for desktop and touch
flows. Set `NODE_PATH` to a runtime containing Playwright, then run it from the
repository root with `node tests/test_ai_explainer_browser.js`.

Automated tests use a fake provider and a mocked Responses HTTP transport. The
seeded live simulation smoke verifies that requested reports preserve sampled
state, Python and NumPy RNG, and trace count/hash; it also verifies zero provider
calls during unrequested turns. They do not require or spend API credits. A live
provider quality/latency evaluation requires configured credentials and model.
